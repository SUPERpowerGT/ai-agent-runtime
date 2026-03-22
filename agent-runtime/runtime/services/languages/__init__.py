"""
Language-specific code analysis adapters.

To add a new language:
1. Create `runtime/services/languages/<language>.py`
2. Implement contract extraction, behavior extraction, and static checks
3. Register a `LanguageAdapter` below

Example next step:
- `runtime/services/languages/javascript.py` is included as a starter template
- register it below when you are ready to turn it on
"""

from __future__ import annotations

from dataclasses import dataclass

from runtime.services.languages.python import (
    extract_behavior_summaries as extract_python_behavior_summaries,
    extract_code_contracts as extract_python_code_contracts,
    check_static_consistency as check_python_static_consistency,
)
# Example future registration:
# from runtime.services.languages.javascript import (
#     extract_behavior_summaries as extract_javascript_behavior_summaries,
#     extract_code_contracts as extract_javascript_code_contracts,
#     check_static_consistency as check_javascript_static_consistency,
# )


@dataclass(frozen=True)
class LanguageAdapter:
    name: str
    extract_code_contracts: callable
    extract_behavior_summaries: callable
    check_static_consistency: callable


_ADAPTERS: dict[str, LanguageAdapter] = {
    "python": LanguageAdapter(
        name="python",
        extract_code_contracts=extract_python_code_contracts,
        extract_behavior_summaries=extract_python_behavior_summaries,
        check_static_consistency=check_python_static_consistency,
    ),
}


def get_language_adapter(language: str | None) -> LanguageAdapter | None:
    """
    Return the registered adapter for a language, if one exists.
    """
    if not language:
        return None
    return _ADAPTERS.get(language)


def list_registered_languages() -> list[str]:
    """
    List languages that currently provide analysis adapters.
    """
    return sorted(_ADAPTERS)


def extract_code_contracts(documents: list[dict]) -> list[dict]:
    """
    Aggregate code contracts from all registered language adapters.
    """
    contracts: list[dict] = []
    for adapter in _ADAPTERS.values():
        contracts.extend(adapter.extract_code_contracts(documents))
    return contracts


def extract_behavior_summaries(documents: list[dict]) -> list[dict]:
    """
    Aggregate behavior summaries from all registered language adapters.
    """
    summaries: list[dict] = []
    for adapter in _ADAPTERS.values():
        summaries.extend(adapter.extract_behavior_summaries(documents))
    return summaries


def check_language_static_consistency(task_spec: dict, code: str) -> str | None:
    """
    Run static consistency checks using the adapter that matches the task language.
    """
    adapter = get_language_adapter(task_spec.get("language"))
    if not adapter:
        return None
    return adapter.check_static_consistency(task_spec, code)
