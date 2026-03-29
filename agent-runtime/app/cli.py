from __future__ import annotations

print("MAIN START")

from concurrent.futures import Future
from pathlib import Path
import sys

from app.printer import (
    print_failure_summary,
    print_generated_code,
    print_runtime_report,
    print_trace_report,
)
from runtime import run_conversation_turn
from state.session_manager import SessionManager


def main() -> None:
    args = sys.argv[1:]
    uploaded_files: list[str] = []
    remaining_args: list[str] = []
    user_id = "user_1"
    conversation_id = None
    turn_id = None
    resume = False
    session_dir = Path(".agent-runtime/sessions")
    session_save_mode = "async"

    index = 0
    while index < len(args):
        if args[index] == "--file" and index + 1 < len(args):
            uploaded_files.append(args[index + 1])
            index += 2
            continue
        if args[index] == "--user-id" and index + 1 < len(args):
            user_id = args[index + 1]
            index += 2
            continue
        if args[index] == "--conversation-id" and index + 1 < len(args):
            conversation_id = args[index + 1]
            index += 2
            continue
        if args[index] == "--turn-id" and index + 1 < len(args):
            turn_id = int(args[index + 1])
            index += 2
            continue
        if args[index] == "--resume":
            resume = True
            index += 1
            continue
        if args[index] == "--session-dir" and index + 1 < len(args):
            session_dir = Path(args[index + 1])
            index += 2
            continue
        if args[index] == "--session-save-mode" and index + 1 < len(args):
            session_save_mode = args[index + 1].strip().lower()
            index += 2
            continue

        remaining_args.append(args[index])
        index += 1

    user_request = (
        " ".join(remaining_args).strip()
        or "write a python function called clamp(value, min_value, max_value) "
           "that returns min_value if value is too small, max_value if value is too "
           "large, otherwise return value. do not use min() or max()"
    )
    if session_save_mode not in {"sync", "async"}:
        raise SystemExit(
            f"unsupported --session-save-mode: {session_save_mode} "
            "(expected: sync or async)"
        )

    manager = SessionManager(session_dir)
    try:
        resolved_conversation_id, resolved_turn_id, existing_state = manager.prepare_state(
            user_id=user_id,
            conversation_id=conversation_id,
            resume=resume,
            user_request=user_request,
            requested_turn_id=turn_id,
        )
    except ValueError as exc:
        raise SystemExit(f"[session] {exc}")

    result = run_conversation_turn(
        user_request,
        state=existing_state,
        user_id=user_id,
        conversation_id=resolved_conversation_id,
        turn_id=resolved_turn_id or 1,
        uploaded_files=uploaded_files,
    )

    session_path = None
    session_save_future: Future[Path] | None = None
    if session_save_mode == "async":
        session_save_future = manager.save_async(result)
    else:
        session_path = manager.save(result)

    print_generated_code(result)
    print_failure_summary(result)
    if session_save_future is not None:
        session_path = session_save_future.result()
    print_runtime_report(result, session_path=session_path)
    print_trace_report(result)

    if result.artifacts.get("runtime_failure") or result.current_turn.get("status") == "failed":
        raise SystemExit(1)
