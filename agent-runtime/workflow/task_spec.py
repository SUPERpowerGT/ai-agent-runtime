from __future__ import annotations

import re


def build_task_spec(user_request: str) -> dict:
    """
    从用户原始请求中提取 workflow 可消费的结构化任务规格。
    这是 workflow 的入口函数，后续 routing / planning 都依赖这份统一规格。
    """
    request_lower = user_request.lower()

    return {
        "language": detect_language(request_lower),
        "artifact_type": detect_artifact_type(request_lower),
        "domain": detect_domain(request_lower),
        "task_mode": detect_task_mode(request_lower),
        "constraints": extract_constraints(user_request, request_lower),
        "requested_public_api": extract_requested_public_api(user_request),
    }


def detect_language(request_lower: str) -> str | None:
    """
    根据用户请求中的语言关键词，推断目标实现语言。
    """
    language_aliases = {
        "python": ["python", "py"],
        "javascript": ["javascript", "js", "node"],
        "typescript": ["typescript", "ts"],
        "java": ["java"],
        "go": ["golang", "go"],
        "rust": ["rust"],
        "c++": ["c++", "cpp"],
        "c": ["language c", " in c", " c program"],
        "c#": ["c#", "csharp", ".net"],
        "ruby": ["ruby"],
        "php": ["php"],
        "kotlin": ["kotlin"],
        "swift": ["swift"],
        "scala": ["scala"],
        "bash": ["bash", "shell script", "sh script"],
        "sql": ["sql"],
    }

    for language, aliases in language_aliases.items():
        for alias in aliases:
            if alias in request_lower:
                return language

    return None


def detect_artifact_type(request_lower: str) -> str:
    """
    推断用户要的产物类型，例如函数、类、接口或脚本。
    """
    if "api" in request_lower or "endpoint" in request_lower or "route" in request_lower:
        return "api"
    if "class" in request_lower:
        return "class"
    if "function" in request_lower or "method" in request_lower:
        return "function"
    if "module" in request_lower or "library" in request_lower:
        return "module"
    if "script" in request_lower:
        return "script"
    return "code"


def detect_domain(request_lower: str) -> str:
    """
    推断任务主要属于哪个领域，用于帮助后续规划和提示词选择。
    """
    if "api" in request_lower or "backend" in request_lower or "server" in request_lower:
        return "backend"
    if "frontend" in request_lower or "react" in request_lower or "ui" in request_lower:
        return "frontend"
    if "sql" in request_lower or "database" in request_lower:
        return "data"
    return "general"


def detect_task_mode(request_lower: str) -> str:
    """
    推断任务模式，例如生成、扩展、优化或重写。
    """
    if "rewrite" in request_lower or "convert" in request_lower or "translate" in request_lower:
        return "rewrite"
    if "optimize" in request_lower or "refactor" in request_lower or "improve" in request_lower:
        return "optimize"
    if "add " in request_lower or "extend" in request_lower:
        return "extend"
    return "generate"


def extract_constraints(user_request: str, request_lower: str) -> list[str]:
    """
    从用户请求中提取显式约束，供后续阶段复用。
    """
    constraints = []

    if "hello world" in request_lower:
        constraints.append("output or represent hello world")

    if "without" in request_lower:
        constraints.append("respect negative constraints from user request")

    quoted_strings = re.findall(r'"([^"]+)"|\'([^\']+)\'', user_request)
    for double_quoted, single_quoted in quoted_strings:
        value = double_quoted or single_quoted
        if value:
            constraints.append(f'preserve requested literal: "{value}"')

    return constraints


def extract_requested_public_api(user_request: str) -> list[dict]:
    """
    提取用户明确要求的公共 API 形态，例如函数名、类名和参数列表。
    """
    requested_api: list[dict] = []
    seen: set[tuple[str, str]] = set()

    patterns = [
        ("function", re.compile(r"\bfunction\s+called\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\((.*?)\)", re.IGNORECASE)),
        ("function", re.compile(r"\bfunction\s+named\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\((.*?)\)", re.IGNORECASE)),
        ("function", re.compile(r"\bmethod\s+called\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\((.*?)\)", re.IGNORECASE)),
        ("class", re.compile(r"\bclass\s+called\s+([a-zA-Z_][a-zA-Z0-9_]*)\b", re.IGNORECASE)),
        ("class", re.compile(r"\bclass\s+named\s+([a-zA-Z_][a-zA-Z0-9_]*)\b", re.IGNORECASE)),
    ]

    for kind, pattern in patterns:
        for match in pattern.finditer(user_request):
            name = match.group(1)
            if not name:
                continue
            key = (kind, name)
            if key in seen:
                continue
            seen.add(key)
            raw_params = match.group(2).strip() if kind == "function" and match.lastindex and match.lastindex >= 2 else ""
            params = split_params(raw_params) if raw_params else []
            requested_api.append({
                "kind": kind,
                "name": name,
                "params": params,
                "arity": len(params),
            })

    return requested_api


def split_params(raw_params: str) -> list[str]:
    """
    将函数参数字符串安全拆分成参数列表，尽量避免括号嵌套导致的误切分。
    """
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
