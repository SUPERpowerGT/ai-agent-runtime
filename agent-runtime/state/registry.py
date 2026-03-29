from __future__ import annotations

import json
from pathlib import Path
from threading import Lock
import time
from typing import Any


class ConversationRegistry:
    """
    File-backed registry for conversation metadata and ownership.
    """

    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "registry.json"
        self._lock = Lock()

    def _read(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"conversations": {}}
        return json.loads(self.path.read_text(encoding="utf-8"))

    def _write(self, payload: dict[str, Any]) -> None:
        self.path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def get(self, conversation_id: str) -> dict[str, Any] | None:
        with self._lock:
            payload = self._read()
            return payload.get("conversations", {}).get(conversation_id)

    def ensure_conversation(
        self,
        *,
        user_id: str,
        conversation_id: str,
        title: str | None = None,
    ) -> dict[str, Any]:
        now = time.time()
        with self._lock:
            payload = self._read()
            conversations = payload.setdefault("conversations", {})
            record = conversations.get(conversation_id)

            if record is None:
                record = {
                    "conversation_id": conversation_id,
                    "user_id": user_id,
                    "title": title or conversation_id,
                    "created_at": now,
                    "updated_at": now,
                    "last_turn_id": 0,
                    "last_summary": "",
                    "session_file": f"{conversation_id}.json",
                }
                conversations[conversation_id] = record
            else:
                if record.get("user_id") != user_id:
                    raise ValueError(
                        f"conversation {conversation_id} belongs to user {record.get('user_id')}, "
                        f"not {user_id}"
                    )
                record["updated_at"] = now
                if title:
                    record["title"] = title

            self._write(payload)
            return dict(record)

    def update_from_state(self, state) -> dict[str, Any]:
        profile_memory = state.memory.get("profile_memory", {})
        title = (
            state.active_user_request().strip().splitlines()[0][:80]
            if state.active_user_request().strip()
            else state.conversation_id
        )
        now = time.time()
        with self._lock:
            payload = self._read()
            conversations = payload.setdefault("conversations", {})
            record = conversations.setdefault(
                state.conversation_id,
                {
                    "conversation_id": state.conversation_id,
                    "user_id": state.user_id,
                    "title": title,
                    "created_at": now,
                    "updated_at": now,
                    "last_turn_id": 0,
                    "last_summary": "",
                    "session_file": f"{state.conversation_id}.json",
                },
            )
            if record.get("user_id") != state.user_id:
                raise ValueError(
                    f"conversation {state.conversation_id} belongs to user {record.get('user_id')}, "
                    f"not {state.user_id}"
                )
            record["updated_at"] = now
            record["last_turn_id"] = state.turn_id
            record["last_summary"] = profile_memory.get("session_summary", "")
            record["title"] = record.get("title") or title
            record["session_file"] = f"{state.conversation_id}.json"
            self._write(payload)
            return dict(record)

    def list_user_conversations(self, user_id: str) -> list[dict[str, Any]]:
        with self._lock:
            payload = self._read()
            conversations = payload.get("conversations", {}).values()
            items = [item for item in conversations if item.get("user_id") == user_id]
            return sorted(items, key=lambda item: item.get("updated_at", 0), reverse=True)

    def delete(self, conversation_id: str) -> bool:
        with self._lock:
            payload = self._read()
            conversations = payload.setdefault("conversations", {})
            removed = conversations.pop(conversation_id, None)
            self._write(payload)
            return removed is not None
