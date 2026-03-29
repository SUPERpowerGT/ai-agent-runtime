from __future__ import annotations

import re

from runtime.services.languages import (
    extract_behavior_summaries,
    extract_code_contracts,
    get_language_adapter,
)
from state.state import TaskState


PREFERENCE_PATTERNS = [
    re.compile(r"\b(?:i prefer|prefer|remember that i prefer)\b(.+)", re.IGNORECASE),
    re.compile(r"\bkeep (?:the )?code\b(.+)", re.IGNORECASE),
]


def build_turn_summary(state: TaskState) -> str:
    """
    Distill the current task run into a short cross-turn summary.
    """
    if state.test_result:
        summary = f"test_result={state.test_result}"
        if state.generated_code:
            summary += ", generated_code=yes"
        return summary

    if state.generated_code:
        return "generated code available"

    research_summary = state.local_memory.get("research")
    if research_summary:
        return f"research={str(research_summary)[:160]}"

    if state.plan:
        return f"plan={state.plan}"

    return "turn completed"


def build_session_summary(state: TaskState, *, limit: int = 6) -> str:
    """
    Build a compact cross-turn session summary from archived turn summaries.
    """
    if not state.history:
        return ""

    lines = []
    for item in state.history[-limit:]:
        turn_id = item.get("turn_id", "?")
        summary = (item.get("summary") or "").strip()
        if summary:
            lines.append(f"turn {turn_id}: {summary}")

    return "\n".join(lines).strip()


def build_turn_status(state: TaskState) -> str:
    """
    Derive a normalized final status for the current turn.
    """
    if state.test_result == "PASS":
        return "completed"
    if state.test_result == "FAIL" or state.error_log:
        return "failed"
    if state.finished:
        return "completed"
    return "active"


def extract_memory_updates(state: TaskState) -> dict[str, str]:
    """
    Extract durable memory from the current turn.
    """
    updates: dict[str, str] = {}
    request = state.active_user_request()

    for pattern in PREFERENCE_PATTERNS:
        match = pattern.search(request)
        if not match:
            continue
        preference = match.group(1).strip(" .")
        if preference:
            updates["preference"] = preference
            break

    if state.uploaded_files:
        updates["uploaded_files"] = ", ".join(state.uploaded_files)

    if state.test_result == "PASS":
        updates["last_success_summary"] = build_turn_summary(state)

    return updates


def extract_code_memory(state: TaskState) -> dict[str, list[dict]]:
    if not state.generated_code:
        return {"code_contracts": [], "behavior_summaries": []}

    language = state.task_spec.get("language")
    extension_map = {
        "python": "py",
        "javascript": "js",
        "typescript": "ts",
    }
    extension = extension_map.get(language, "py")
    documents = [{
        "source": f"{state.conversation_id}_turn_{state.current_turn_id()}.{extension}",
        "text": state.generated_code,
    }]
    adapter = get_language_adapter(language) if language else None
    if adapter is not None:
        return {
            "code_contracts": adapter.extract_code_contracts(documents),
            "behavior_summaries": adapter.extract_behavior_summaries(documents),
        }

    return {
        "code_contracts": extract_code_contracts(documents),
        "behavior_summaries": extract_behavior_summaries(documents),
    }


def finalize_turn_state(state: TaskState) -> TaskState:
    """
    Compatibility helper for turn rollover.
    This persists the finished turn and then clears transient workspace state
    so the next turn can start cleanly.
    """
    persist_turn_memory_and_history(state)
    prepare_state_for_next_turn(state)
    return state


def persist_turn_memory_and_history(state: TaskState) -> TaskState:
    """
    Persist summary + memory for the current turn without clearing outputs.
    Safe to call multiple times for the same turn.
    """
    summary = build_turn_summary(state)
    for key, value in extract_memory_updates(state).items():
        state.remember_memory(key, value)

    state.mark_current_turn_finished(
        status=build_turn_status(state),
        summary=summary,
    )
    state.archive_current_turn(summary=summary)
    state.remember_episode(
        summary=summary,
        status=build_turn_status(state),
        turn_id=state.current_turn_id(),
    )
    code_memory = extract_code_memory(state)
    if code_memory["code_contracts"]:
        state.remember_memory("last_code_contracts", code_memory["code_contracts"])
    if code_memory["behavior_summaries"]:
        state.remember_memory("last_behavior_summaries", code_memory["behavior_summaries"])
    session_summary = build_session_summary(state)
    if session_summary:
        state.remember_memory("session_summary", session_summary)
    return state


def prepare_state_for_next_turn(state: TaskState) -> TaskState:
    """
    Clear transient workspace fields before the next turn starts.
    """
    state.clear_transient_task_state()
    return state
