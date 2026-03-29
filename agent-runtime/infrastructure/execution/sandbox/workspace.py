from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
import inspect
import json
import shutil
import sys
import tempfile


@dataclass(frozen=True)
class SandboxWorkspace:
    root: str
    command: list[str]
    entrypoint: str
    original_available: bool = False


@contextmanager
def create_sandbox_workspace(
    *,
    language: str | None,
    code: str,
    task_spec: dict,
    uploaded_files: list[str] | None = None,
):
    """
    Materialize generated code into a temporary workspace that the execution
    tool can treat as a restricted sandbox root.
    """
    sandbox_dir = tempfile.mkdtemp(prefix="agent-runtime-sandbox-")

    try:
        workspace = _build_workspace(
            root=Path(sandbox_dir),
            language=language,
            code=code,
            task_spec=task_spec,
            uploaded_files=uploaded_files or [],
        )
        yield workspace
    finally:
        shutil.rmtree(sandbox_dir, ignore_errors=True)


def _build_workspace(
    *,
    root: Path,
    language: str | None,
    code: str,
    task_spec: dict,
    uploaded_files: list[str],
) -> SandboxWorkspace:
    normalized_language = (language or "").lower()

    if normalized_language == "python":
        module_path = root / "generated_module.py"
        original_module_path = root / "original_module.py"
        harness_path = root / "smoke_test.py"
        spec_path = root / "task_spec.json"

        module_path.write_text(code, encoding="utf-8")
        original_sources = _collect_python_sources(uploaded_files)
        if original_sources:
            original_module_path.write_text(
                _build_original_module(original_sources),
                encoding="utf-8",
            )
        spec_path.write_text(
            json.dumps(task_spec, ensure_ascii=True, indent=2),
            encoding="utf-8",
        )
        harness_path.write_text(
            _build_python_harness(
                task_spec,
                original_available=bool(original_sources),
            ),
            encoding="utf-8",
        )

        return SandboxWorkspace(
            root=str(root),
            command=[sys.executable, harness_path.name],
            entrypoint=harness_path.name,
            original_available=bool(original_sources),
        )

    raise ValueError(
        "Sandbox execution is not supported yet for language: "
        f"{language or 'unspecified'}"
    )


def _build_python_harness(task_spec: dict, *, original_available: bool) -> str:
    contracts = task_spec.get("code_contracts", [])
    behavior_summaries = task_spec.get("behavior_summaries", [])
    requested_public_api = task_spec.get("requested_public_api", [])

    contract_names = [contract["name"] for contract in contracts if contract.get("name")]
    requested_function_names = [
        item["name"]
        for item in requested_public_api
        if item.get("kind") == "function" and item.get("name")
    ]
    requested_function_specs = [
        item
        for item in requested_public_api
        if item.get("kind") == "function" and item.get("name")
    ]
    behavior_map = {
        summary["name"]: summary
        for summary in behavior_summaries
        if summary.get("name")
    }
    expected_signature_map = {
        item["name"]: item.get("params", [])
        for item in contracts + requested_function_specs
        if item.get("name")
    }

    return f"""import importlib
import inspect

module = importlib.import_module("generated_module")
ORIGINAL_AVAILABLE = {original_available!r}
original_module = importlib.import_module("original_module") if ORIGINAL_AVAILABLE else None

EXPECTED_FUNCTIONS = {sorted(dict.fromkeys(contract_names + requested_function_names))!r}
BEHAVIOR_MAP = {behavior_map!r}
CONTRACTS = {contracts!r}
EXPECTED_SIGNATURES = {expected_signature_map!r}


def _sample_value(param_name):
    lowered = param_name.lower()
    if any(token in lowered for token in ("profile", "user", "payload", "record", "data")):
        return {{"name": "Alice", "role": "admin", "active": True, "user_id": "user-1"}}
    if "items" in lowered:
        return [
            {{"price": 10.0, "quantity": 2}},
            {{"price": 5.5, "quantity": 1}},
        ]
    if "discount" in lowered or "rate" in lowered:
        return 0.1
    if "total" in lowered or "amount" in lowered or "value" in lowered:
        return 100.0
    if "count" in lowered or "index" in lowered:
        return 1
    if any(token in lowered for token in ("name", "id", "key", "label", "title")):
        return "sample"
    if any(token in lowered for token in ("enabled", "active", "flag")):
        return True
    return 1


def _build_args(contract):
    args = []
    for raw_param in contract.get("params", []):
        param_name = raw_param.split(":", 1)[0].split("=", 1)[0].strip()
        args.append(_sample_value(param_name))
    return args


def _normalize_param_name(raw_param):
    value = raw_param.strip()
    if not value:
        return value
    value = value.split(":", 1)[0].strip()
    value = value.split("=", 1)[0].strip()
    return value.lstrip("*")


def main():
    for function_name in EXPECTED_FUNCTIONS:
        if not hasattr(module, function_name):
            raise AssertionError(f"missing expected function: {{function_name}}")

        function_object = getattr(module, function_name)
        if getattr(function_object, "__name__", "") == "<lambda>":
            raise AssertionError(f"public function {{function_name}} must not be implemented as lambda")

        expected_params = EXPECTED_SIGNATURES.get(function_name, [])
        if expected_params:
            actual_signature = inspect.signature(function_object)
            actual_params = [param.name for param in actual_signature.parameters.values()]
            normalized_expected = [_normalize_param_name(param) for param in expected_params]
            if actual_params != normalized_expected:
                raise AssertionError(
                    f"signature mismatch for {{function_name}}: expected={{normalized_expected!r}} actual={{actual_params!r}}"
                )

    for function_name in EXPECTED_FUNCTIONS:
        contract = next(
            (
                item
                for item in CONTRACTS
                if item.get("name") == function_name
            ),
            None,
        )
        if contract is None:
            contract = {{
                "name": function_name,
                "params": EXPECTED_SIGNATURES.get(function_name, []),
            }}
        if contract is None:
            continue

        func = getattr(module, function_name)
        args = _build_args(contract)
        result = func(*args)

        if ORIGINAL_AVAILABLE and hasattr(original_module, function_name):
            original_result = getattr(original_module, function_name)(*args)
            if result != original_result:
                raise AssertionError(
                    f"behavior mismatch for {{function_name}}: generated={{result!r}} original={{original_result!r}}"
                )

        if function_name in BEHAVIOR_MAP:
            summary = BEHAVIOR_MAP[function_name]
            body_preview = summary.get("body_preview", "")
            if "round(" in body_preview and result is not None:
                float(result)
            if "return" in body_preview and result is None:
                raise AssertionError(f"function {{function_name}} returned None unexpectedly")

    print("SANDBOX_SMOKE_TEST_PASS")


if __name__ == "__main__":
    main()
"""


def _collect_python_sources(uploaded_files: list[str]) -> list[tuple[str, str]]:
    sources: list[tuple[str, str]] = []

    for file_path in uploaded_files:
        if not file_path.endswith(".py"):
            continue

        path = Path(file_path)
        if not path.exists():
            continue

        sources.append((path.name, path.read_text(encoding="utf-8")))

    return sources


def _build_original_module(sources: list[tuple[str, str]]) -> str:
    segments = []

    for source_name, source_text in sources:
        segments.append(f"# source: {source_name}\n{source_text.strip()}\n")

    return "\n\n".join(segments).strip() + "\n"
