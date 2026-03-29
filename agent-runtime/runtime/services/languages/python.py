from __future__ import annotations

import re


def extract_code_contracts(documents: list[dict]) -> list[dict]:
    contracts = []
    function_pattern = re.compile(
        r"^def\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\((.*?)\)\s*(?:->\s*[^:]+)?\s*:",
        re.MULTILINE,
    )

    for document in documents:
        source = document["source"]
        if not source.endswith(".py"):
            continue

        for match in function_pattern.finditer(document["text"]):
            function_name = match.group(1)
            raw_params = match.group(2).strip()
            params = split_params(raw_params)

            contracts.append({
                "language": "python",
                "source": source,
                "name": function_name,
                "params": params,
                "arity": len(params),
                "signature": f"{function_name}({', '.join(params)})",
            })

    return contracts


def extract_behavior_summaries(documents: list[dict]) -> list[dict]:
    summaries = []
    function_pattern = re.compile(
        r"^def\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\((.*?)\)\s*(?:->\s*[^:]+)?\s*:\n((?:[ \t]+.*\n?)*)",
        re.MULTILINE,
    )

    for document in documents:
        source = document["source"]
        if not source.endswith(".py"):
            continue

        for match in function_pattern.finditer(document["text"]):
            function_name = match.group(1)
            raw_params = match.group(2).strip()
            params = split_params(raw_params)
            body = match.group(3).strip("\n")
            normalized_body = normalize_function_body(body)

            if not normalized_body:
                continue

            function_bodies = {function_name: extract_body_lines(body)}
            returned_keys = sorted(extract_returned_dict_keys(function_bodies).get(function_name, set()))
            key_accesses = sorted(extract_key_access_patterns(function_bodies).get(function_name, set()))

            summaries.append({
                "language": "python",
                "source": source,
                "name": function_name,
                "params": params,
                "body_preview": normalized_body,
                "returned_keys": returned_keys,
                "key_accesses": key_accesses,
            })

    return summaries


def check_static_consistency(task_spec: dict, code: str) -> str | None:
    function_bodies = extract_function_bodies(code)
    if not function_bodies:
        return None

    behavior_failure = check_behavior_regression(task_spec, function_bodies)
    if behavior_failure:
        return behavior_failure

    producer_summaries = build_expected_producers(task_spec)
    if not producer_summaries:
        return None

    for consumer_name, body_lines in function_bodies.items():
        parameter_names = extract_function_parameters(code, consumer_name)
        if not parameter_names:
            continue

        accesses = sorted(extract_key_access_patterns({"_": body_lines}).get("_", set()))
        for variable_name, key_name in accesses:
            if variable_name not in parameter_names:
                continue

            matched_producer_keys = match_producer_keys(variable_name, producer_summaries)
            if matched_producer_keys and key_name not in matched_producer_keys:
                return (
                    f"Cross-function consistency check failed: {consumer_name} accesses "
                    f'{variable_name}["{key_name}"] but matching producer keys are {sorted(matched_producer_keys)}'
                )

    return None


def check_behavior_regression(task_spec: dict, function_bodies: dict[str, list[str]]) -> str | None:
    """
    Compare generated function bodies against lightweight access patterns extracted
    from the original uploaded code. This is intentionally heuristic: it aims to
    catch obvious behavior drift in optimize/rewrite tasks without requiring full AST
    execution.
    """
    task_mode = task_spec.get("task_mode", "generate")
    if task_mode not in {"optimize", "rewrite"}:
        return None

    expected_accesses = build_expected_access_patterns(task_spec)
    if not expected_accesses:
        return None

    generated_accesses = extract_key_access_patterns(function_bodies)

    for function_name, required_accesses in expected_accesses.items():
        if function_name not in function_bodies:
            continue

        actual_accesses = set(generated_accesses.get(function_name, set()))
        missing_accesses = sorted(required_accesses - actual_accesses)
        if missing_accesses:
            missing_text = ", ".join(
                f'{variable}["{key}"]' for variable, key in missing_accesses
            )
            return (
                f"Behavior regression check failed: {function_name} no longer uses "
                f"expected access pattern(s): {missing_text}"
            )

    return None


def split_params(raw_params: str) -> list[str]:
    if not raw_params:
        return []

    params = []
    current = []
    bracket_depth = 0

    for char in raw_params:
        if char in "([{":
            bracket_depth += 1
        elif char in ")]}":
            bracket_depth = max(0, bracket_depth - 1)

        if char == "," and bracket_depth == 0:
            param = "".join(current).strip()
            if param:
                params.append(param)
            current = []
            continue

        current.append(char)

    tail = "".join(current).strip()
    if tail:
        params.append(tail)

    return params


def normalize_function_body(body: str, max_lines: int = 8) -> str:
    lines = []

    for line in body.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith('"""') or stripped.startswith("'''"):
            continue
        lines.append(stripped)

    return " | ".join(lines[:max_lines])


def extract_body_lines(body: str) -> list[str]:
    lines = []

    for line in body.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        lines.append(stripped)

    return lines


def extract_function_bodies(code: str) -> dict[str, list[str]]:
    function_bodies: dict[str, list[str]] = {}
    current_function = None
    current_indent = None

    for line in code.splitlines():
        stripped = line.strip()
        function_match = re.match(r"^def\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(", stripped)
        if function_match:
            current_function = function_match.group(1)
            current_indent = None
            function_bodies[current_function] = []
            continue

        if current_function is None or not stripped:
            continue

        indent = len(line) - len(line.lstrip(" "))
        if current_indent is None and indent > 0:
            current_indent = indent

        if current_indent is not None and indent < current_indent:
            current_function = None
            current_indent = None
            continue

        if current_function is not None:
            function_bodies[current_function].append(stripped)

    return function_bodies


def extract_indexed_key_access(function_bodies: dict[str, list[str]]) -> dict[str, set[tuple[str, str]]]:
    access_map: dict[str, set[tuple[str, str]]] = {}

    for function_name, body_lines in function_bodies.items():
        body_text = "\n".join(body_lines)
        accesses = set(re.findall(
            r'([a-zA-Z_][a-zA-Z0-9_]*)\s*\[\s*["\']([a-zA-Z_][a-zA-Z0-9_]*)["\']\s*\]',
            body_text,
        ))
        if accesses:
            access_map[function_name] = accesses

    return access_map


def extract_method_key_access(function_bodies: dict[str, list[str]]) -> dict[str, set[tuple[str, str]]]:
    access_map: dict[str, set[tuple[str, str]]] = {}

    for function_name, body_lines in function_bodies.items():
        body_text = "\n".join(body_lines)
        accesses = set(re.findall(
            r'([a-zA-Z_][a-zA-Z0-9_]*)\s*\.get\(\s*["\']([a-zA-Z_][a-zA-Z0-9_]*)["\']',
            body_text,
        ))
        if accesses:
            access_map[function_name] = accesses

    return access_map


def extract_key_access_patterns(function_bodies: dict[str, list[str]]) -> dict[str, set[tuple[str, str]]]:
    combined: dict[str, set[tuple[str, str]]] = {}
    indexed = extract_indexed_key_access(function_bodies)
    method = extract_method_key_access(function_bodies)

    for function_name in set(indexed) | set(method):
        combined[function_name] = set()
        combined[function_name].update(indexed.get(function_name, set()))
        combined[function_name].update(method.get(function_name, set()))

    return combined


def extract_returned_dict_keys(function_bodies: dict[str, list[str]]) -> dict[str, set[str]]:
    returned_keys: dict[str, set[str]] = {}

    for function_name, body_lines in function_bodies.items():
        body_text = "\n".join(body_lines)
        dict_keys = set(re.findall(r'["\']([a-zA-Z_][a-zA-Z0-9_]*)["\']\s*:', body_text))
        if dict_keys:
            returned_keys[function_name] = dict_keys

    return returned_keys


def build_expected_producers(task_spec: dict) -> list[dict]:
    producers = []

    for summary in task_spec.get("behavior_summaries", []):
        if summary.get("language") not in {None, "python"}:
            continue

        keys = set(summary.get("returned_keys", []))
        if keys:
            producers.append({
                "function_name": summary["name"],
                "keys": keys,
            })

    return producers


def build_expected_access_patterns(task_spec: dict) -> dict[str, set[tuple[str, str]]]:
    expected_patterns: dict[str, set[tuple[str, str]]] = {}

    for summary in task_spec.get("behavior_summaries", []):
        if summary.get("language") not in {None, "python"}:
            continue

        accesses = {
            tuple(item)
            for item in summary.get("key_accesses", [])
            if isinstance(item, (list, tuple)) and len(item) == 2
        }
        if accesses:
            expected_patterns[summary["name"]] = accesses

    return expected_patterns


def extract_function_parameters(code: str, function_name: str) -> list[str]:
    pattern = re.compile(
        rf"def\s+{re.escape(function_name)}\s*\((.*?)\)\s*(?:->\s*[^:]+)?\s*:"
    )
    match = pattern.search(code)
    if not match:
        return []

    raw_params = match.group(1).strip()
    if not raw_params:
        return []

    params = []
    for raw_param in split_params(raw_params):
        param_name = raw_param.split(":", 1)[0].split("=", 1)[0].strip()
        if param_name:
            params.append(param_name)

    return params


def match_producer_keys(variable_name: str, producers: list[dict]) -> set[str]:
    if variable_name in {"profile", "user", "user_profile"}:
        for producer in producers:
            if producer["function_name"] == "load_user_profile":
                return producer["keys"]

    return set()
