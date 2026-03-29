from __future__ import annotations

import json
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
SESSION_PATH = ROOT_DIR.parent / ".agent-runtime" / "example-sessions" / "multi-turn-demo.json"


def main() -> None:
    if not SESSION_PATH.exists():
        raise SystemExit(f"session file not found: {SESSION_PATH}")

    payload = json.loads(SESSION_PATH.read_text(encoding="utf-8"))

    print("=== Multi-Turn Session Inspection ===")
    print(f"session_path: {SESSION_PATH}")
    print(f"user_id: {payload.get('user_id')}")
    print(f"conversation_id: {payload.get('conversation_id')}")
    print(f"turn_id: {payload.get('turn_id')}")
    print(f"latest_user_message: {payload.get('latest_user_message')}")
    history = payload.get("history", [])
    memory = payload.get("memory", {})
    current_turn = payload.get("current_turn", {})
    profile_memory = memory.get("profile_memory", memory if isinstance(memory, dict) else {})
    episodic_memory = memory.get("episodic_memory", [])
    vector_memory = memory.get("vector_memory", [])
    print(f"history_count: {len(history)}")
    print(f"conversation_log_count: {len(payload.get('conversation_log', []))}")
    print(f"profile_memory_keys: {sorted(profile_memory.keys())}")
    print(f"episodic_memory_count: {len(episodic_memory)}")
    print(f"vector_memory_count: {len(vector_memory)}")
    if profile_memory.get("session_summary"):
        print("session_summary:")
        for line in str(profile_memory["session_summary"]).splitlines():
            print(f"  {line}")

    if history:
        print("history_summaries:")
        for item in history:
            print(f"  - turn {item.get('turn_id')}: {item.get('summary')}")

    print("workspace:")
    print(f"current_turn: {current_turn}")
    print("session:")
    print({
        "user_id": payload.get("user_id"),
        "conversation_id": payload.get("conversation_id"),
        "turn_id": payload.get("turn_id"),
        "profile_memory_keys": sorted(profile_memory.keys()),
        "episodic_memory_count": len(episodic_memory),
        "vector_memory_count": len(vector_memory),
        "history_count": len(history),
        "conversation_log_count": len(payload.get("conversation_log", [])),
    })

    print("validation:")
    print(f"  - turn_is_3: {payload.get('turn_id') == 3}")
    print(f"  - history_has_at_least_2_entries: {len(history) >= 2}")
    print(f"  - current_turn_matches_turn_3: {current_turn.get('turn_id') == 3}")


if __name__ == "__main__":
    main()
