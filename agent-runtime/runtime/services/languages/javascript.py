from __future__ import annotations


def extract_code_contracts(documents: list[dict]) -> list[dict]:
    """
    Extract JavaScript/TypeScript function or module contracts from uploaded documents.

    Template notes:
    - Filter supported source files such as `.js`, `.mjs`, `.cjs`, `.ts`
    - Return a list of contract dicts with a stable shape:
      {
          "language": "javascript",
          "source": "...",
          "name": "...",
          "params": [...],
          "arity": 2,
          "signature": "foo(a, b)",
      }
    """
    return []


def extract_behavior_summaries(documents: list[dict]) -> list[dict]:
    """
    Extract lightweight behavior summaries from uploaded JavaScript/TypeScript code.

    Template notes:
    - Reuse the same function discovery logic as contract extraction
    - Keep summaries short and checker-friendly
    - Return a list of dicts like:
      {
          "language": "javascript",
          "source": "...",
          "name": "...",
          "params": [...],
          "body_preview": "...",
      }
    """
    return []


def check_static_consistency(task_spec: dict, code: str) -> str | None:
    """
    Run JavaScript/TypeScript-specific static consistency checks.

    Template notes:
    - Start with deterministic checks only
    - Prefer catching obvious contract mismatches before adding heavier logic
    - Return None when no issue is found, otherwise return a short failure reason
    """
    return None
