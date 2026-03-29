from __future__ import annotations


def _clean_text(text: str) -> str:
    return " ".join(text.split())


def preview_text(text: str, limit: int = 120) -> str:
    cleaned = _clean_text(text)
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 3] + "..."


def log_runtime(message: str) -> None:
    print(f"[runtime] {message}")


def log_agent(agent_name: str, message: str) -> None:
    print(f"[agent:{agent_name}] {message}")


def log_llm(agent_name: str, duration_ms: float, content: str) -> None:
    preview = preview_text(content)
    print(f"[llm:{agent_name}] {duration_ms:.2f} ms | {preview}")


def log_tool(tool_name: str, message: str) -> None:
    print(f"[tool:{tool_name}] {message}")
