from __future__ import annotations

import ast
from dataclasses import dataclass
import re


def apply_contract_transformations(task_spec: dict, code: str) -> str:
    """
    Apply pre-test contract normalization rules in a fixed order.

    The pipeline is rule-based so additional transforms can be layered in later.
    Python transforms already use the standard-library AST for semantic-safe
    renames. JavaScript/TypeScript currently fall back to textual transforms
    until a dedicated parser is introduced.
    """
    transformed = code

    for rule in _build_rules():
        if not rule.supports(task_spec):
            continue
        transformed = rule.apply(task_spec, transformed)

    return transformed


def preserve_public_api_names(task_spec: dict, code: str) -> str:
    """
    Backward-compatible wrapper for the older entry point.
    """
    return apply_contract_transformations(task_spec, code)


@dataclass(frozen=True)
class CodeTransformRule:
    name: str

    def supports(self, task_spec: dict) -> bool:
        raise NotImplementedError

    def apply(self, task_spec: dict, code: str) -> str:
        raise NotImplementedError


class PreservePythonPublicApiRule(CodeTransformRule):
    def supports(self, task_spec: dict) -> bool:
        return _supports_contract_preservation(task_spec, {"python"})

    def apply(self, task_spec: dict, code: str) -> str:
        contracts = task_spec.get("code_contracts", [])
        if not contracts:
            return code

        try:
            tree = ast.parse(code)
        except SyntaxError:
            return code

        function_signatures = _extract_python_function_signatures(tree)
        rename_map = _build_python_function_rename_map(contracts, function_signatures)
        if not rename_map:
            return code

        transformer = PythonPublicApiTransformer(rename_map=rename_map)
        updated_tree = transformer.visit(tree)
        ast.fix_missing_locations(updated_tree)
        return ast.unparse(updated_tree)


class PreservePythonParameterNamesRule(CodeTransformRule):
    def supports(self, task_spec: dict) -> bool:
        return _supports_contract_preservation(task_spec, {"python"})

    def apply(self, task_spec: dict, code: str) -> str:
        contracts = task_spec.get("code_contracts", [])
        if not contracts:
            return code

        try:
            tree = ast.parse(code)
        except SyntaxError:
            return code

        function_signatures = _extract_python_function_signatures(tree)
        rename_map = _build_python_parameter_rename_map(contracts, function_signatures)
        if not rename_map:
            return code

        transformer = PythonParameterTransformer(rename_map=rename_map)
        updated_tree = transformer.visit(tree)
        ast.fix_missing_locations(updated_tree)
        return ast.unparse(updated_tree)


class PreserveJavascriptPublicApiRule(CodeTransformRule):
    def supports(self, task_spec: dict) -> bool:
        return _supports_contract_preservation(task_spec, {"javascript", "typescript"})

    def apply(self, task_spec: dict, code: str) -> str:
        contracts = task_spec.get("code_contracts", [])
        if not contracts:
            return code

        signatures = _extract_javascript_signatures(code)
        if not signatures:
            return code

        expected_names = {contract["name"] for contract in contracts}
        rename_map: dict[str, str] = {}

        for contract in contracts:
            expected_name = contract["name"]
            expected_arity = contract["arity"]
            if expected_name in signatures:
                continue

            normalized_expected = _normalize_api_name(expected_name)
            for actual_name, actual_signature in signatures.items():
                if actual_name in expected_names or actual_name in rename_map:
                    continue
                if actual_signature["arity"] != expected_arity:
                    continue
                if _normalize_api_name(actual_name) != normalized_expected:
                    continue

                rename_map[actual_name] = expected_name
                break

        if not rename_map:
            return code

        updated_code = code
        for actual_name, expected_name in rename_map.items():
            updated_code = re.sub(rf"\b{re.escape(actual_name)}\b", expected_name, updated_code)

        return updated_code


class PreserveJavascriptParameterNamesRule(CodeTransformRule):
    def supports(self, task_spec: dict) -> bool:
        return _supports_contract_preservation(task_spec, {"javascript", "typescript"})

    def apply(self, task_spec: dict, code: str) -> str:
        contracts = task_spec.get("code_contracts", [])
        if not contracts:
            return code

        signatures = _extract_javascript_signatures(code)
        if not signatures:
            return code

        updated_code = code
        for contract in contracts:
            function_name = contract["name"]
            signature = signatures.get(function_name)
            if not signature:
                continue

            expected_params = [_extract_param_name(param) for param in contract.get("params", [])]
            actual_params = signature["params"]
            if len(expected_params) != len(actual_params):
                continue

            rename_pairs = [
                (actual_name, expected_name)
                for actual_name, expected_name in zip(actual_params, expected_params)
                if actual_name and expected_name and actual_name != expected_name
            ]
            if not rename_pairs:
                continue

            updated_code = _replace_javascript_function_params(
                code=updated_code,
                function_name=function_name,
                expected_params=expected_params,
            )

            for actual_name, expected_name in rename_pairs:
                updated_code = re.sub(rf"\b{re.escape(actual_name)}\b", expected_name, updated_code)

        return updated_code


class PythonPublicApiTransformer(ast.NodeTransformer):
    def __init__(self, *, rename_map: dict[str, str]):
        self.rename_map = rename_map

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.AST:
        node = self.generic_visit(node)
        node.name = self.rename_map.get(node.name, node.name)
        return node

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> ast.AST:
        node = self.generic_visit(node)
        node.name = self.rename_map.get(node.name, node.name)
        return node

    def visit_Name(self, node: ast.Name) -> ast.AST:
        if node.id in self.rename_map:
            node.id = self.rename_map[node.id]
        return node


class PythonParameterTransformer(ast.NodeTransformer):
    def __init__(self, *, rename_map: dict[str, dict[str, str]]):
        self.rename_map = rename_map
        self.current_function_stack: list[str] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.AST:
        self.current_function_stack.append(node.name)
        node = self.generic_visit(node)
        self.current_function_stack.pop()
        return node

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> ast.AST:
        self.current_function_stack.append(node.name)
        node = self.generic_visit(node)
        self.current_function_stack.pop()
        return node

    def visit_arg(self, node: ast.arg) -> ast.AST:
        current_function = self.current_function_stack[-1] if self.current_function_stack else None
        if current_function and current_function in self.rename_map:
            node.arg = self.rename_map[current_function].get(node.arg, node.arg)
        return node

    def visit_Name(self, node: ast.Name) -> ast.AST:
        current_function = self.current_function_stack[-1] if self.current_function_stack else None
        if current_function and current_function in self.rename_map:
            node.id = self.rename_map[current_function].get(node.id, node.id)
        return node


def _build_rules() -> list[CodeTransformRule]:
    return [
        PreservePythonPublicApiRule(name="preserve_python_public_api"),
        PreservePythonParameterNamesRule(name="preserve_python_parameter_names"),
        PreserveJavascriptPublicApiRule(name="preserve_javascript_public_api"),
        PreserveJavascriptParameterNamesRule(name="preserve_javascript_parameter_names"),
    ]


def _supports_contract_preservation(task_spec: dict, languages: set[str]) -> bool:
    return (
        task_spec.get("task_mode", "generate") in {"extend", "optimize", "rewrite"}
        and task_spec.get("language") in languages
        and bool(task_spec.get("code_contracts"))
    )


def _extract_python_function_signatures(tree: ast.AST) -> dict[str, list[str]]:
    signatures: dict[str, list[str]] = {}

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue

        params = [arg.arg for arg in node.args.posonlyargs]
        params.extend(arg.arg for arg in node.args.args)
        if node.args.vararg:
            params.append(node.args.vararg.arg)
        params.extend(arg.arg for arg in node.args.kwonlyargs)
        if node.args.kwarg:
            params.append(node.args.kwarg.arg)

        signatures[node.name] = params

    return signatures


def _build_python_function_rename_map(
    contracts: list[dict],
    function_signatures: dict[str, list[str]],
) -> dict[str, str]:
    expected_names = {contract["name"] for contract in contracts}
    rename_map: dict[str, str] = {}

    for contract in contracts:
        expected_name = contract["name"]
        expected_arity = contract["arity"]
        if expected_name in function_signatures:
            continue

        normalized_expected = _normalize_api_name(expected_name)
        for actual_name, actual_params in function_signatures.items():
            if actual_name in expected_names or actual_name in rename_map:
                continue
            if len(actual_params) != expected_arity:
                continue
            if _normalize_api_name(actual_name) != normalized_expected:
                continue

            rename_map[actual_name] = expected_name
            break

    return rename_map


def _build_python_parameter_rename_map(
    contracts: list[dict],
    function_signatures: dict[str, list[str]],
) -> dict[str, dict[str, str]]:
    rename_map: dict[str, dict[str, str]] = {}

    for contract in contracts:
        function_name = contract["name"]
        actual_params = function_signatures.get(function_name)
        if not actual_params:
            continue

        expected_params = [_extract_param_name(param) for param in contract.get("params", [])]
        if len(actual_params) != len(expected_params):
            continue

        function_rename_map = {
            actual_name: expected_name
            for actual_name, expected_name in zip(actual_params, expected_params)
            if actual_name != expected_name
        }
        if function_rename_map:
            rename_map[function_name] = function_rename_map

    return rename_map


def _extract_javascript_signatures(code: str) -> dict[str, dict[str, object]]:
    signatures: dict[str, dict[str, object]] = {}
    patterns = [
        re.compile(r"\b(?:async\s+)?function\s+([a-zA-Z_$][\w$]*)\s*\((.*?)\)", re.DOTALL),
        re.compile(r"\b(?:const|let|var)\s+([a-zA-Z_$][\w$]*)\s*=\s*(?:async\s*)?\((.*?)\)\s*=>", re.DOTALL),
        re.compile(r"\b(?:const|let|var)\s+([a-zA-Z_$][\w$]*)\s*=\s*(?:async\s*)?function\s*\((.*?)\)", re.DOTALL),
    ]

    for pattern in patterns:
        for match in pattern.finditer(code):
            params = _split_params(match.group(2))
            signatures[match.group(1)] = {
                "arity": len(params),
                "params": params,
            }

    return signatures


def _replace_javascript_function_params(code: str, function_name: str, expected_params: list[str]) -> str:
    replacements = [
        (
            re.compile(
                rf"(\b(?:async\s+)?function\s+{re.escape(function_name)}\s*\()(?P<params>.*?)(\))",
                re.DOTALL,
            ),
            rf"\1{', '.join(expected_params)}\3",
        ),
        (
            re.compile(
                rf"(\b(?:const|let|var)\s+{re.escape(function_name)}\s*=\s*(?:async\s*)?\()(?P<params>.*?)(\)\s*=>)",
                re.DOTALL,
            ),
            rf"\1{', '.join(expected_params)}\3",
        ),
        (
            re.compile(
                rf"(\b(?:const|let|var)\s+{re.escape(function_name)}\s*=\s*(?:async\s*)?function\s*\()(?P<params>.*?)(\))",
                re.DOTALL,
            ),
            rf"\1{', '.join(expected_params)}\3",
        ),
    ]

    updated_code = code
    for pattern, replacement in replacements:
        updated_code, count = pattern.subn(replacement, updated_code, count=1)
        if count:
            return updated_code

    return updated_code


def _split_params(raw_params: str) -> list[str]:
    raw_params = raw_params.strip()
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


def _extract_param_name(param: str) -> str:
    value = param.strip()
    if not value:
        return value

    value = value.split(":", 1)[0].strip()
    value = value.split("=", 1)[0].strip()
    return value.lstrip("*")


def _normalize_api_name(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "", name).lower()
