import re


def build_task_spec(user_request: str) -> dict:
    """
    从用户请求中提取可复用的任务规格。
    """
    request_lower = user_request.lower()

    return {
        "language": detect_language(request_lower),
        "artifact_type": detect_artifact_type(request_lower),
        "domain": detect_domain(request_lower),
        "constraints": extract_constraints(user_request, request_lower),
    }


def detect_language(request_lower: str) -> str | None:
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
    if "api" in request_lower or "backend" in request_lower or "server" in request_lower:
        return "backend"
    if "frontend" in request_lower or "react" in request_lower or "ui" in request_lower:
        return "frontend"
    if "sql" in request_lower or "database" in request_lower:
        return "data"
    return "general"


def extract_constraints(user_request: str, request_lower: str) -> list[str]:
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
