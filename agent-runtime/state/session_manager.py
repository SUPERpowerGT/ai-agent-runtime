from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path
from threading import Lock
import time
from typing import Any

from state.registry import ConversationRegistry
from state.store import SessionStore


def _build_conversation_id(user_id: str) -> str:
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    return f"{user_id}-{timestamp}"


class SessionManager:
    """
    Owns session persistence, conversation metadata, and user/conversation validation.
    """

    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.store = SessionStore(self.root)
        self.registry = ConversationRegistry(self.root)
        self._executor = ThreadPoolExecutor(
            max_workers=1,
            thread_name_prefix="session-manager",
        )
        self._lock = Lock()

    def resolve_conversation_id(
        self,
        *,
        user_id: str,
        conversation_id: str | None,
        resume: bool,
    ) -> str:
        if conversation_id:
            return conversation_id

        if resume:
            existing = self.registry.list_user_conversations(user_id)
            if existing:
                return existing[0]["conversation_id"]
            raise ValueError(f"no saved conversations found for user {user_id}")

        return _build_conversation_id(user_id)

    def load_state(
        self,
        *,
        user_id: str,
        conversation_id: str,
        strict: bool = True,
    ):
        record = self.registry.get(conversation_id)
        if record is None:
            if not self.store.exists(conversation_id):
                return None
            raise ValueError(
                f"session file exists for {conversation_id} but registry metadata is missing"
            )

        if record.get("user_id") != user_id:
            raise ValueError(
                f"conversation {conversation_id} belongs to user {record.get('user_id')}, not {user_id}"
            )

        if not self.store.exists(conversation_id):
            if not strict:
                self.registry.delete(conversation_id)
                return None
            raise ValueError(
                f"registry contains conversation {conversation_id} but session file is missing"
            )

        return self.store.load(conversation_id)

    def prepare_state(
        self,
        *,
        user_id: str,
        conversation_id: str | None,
        resume: bool,
        user_request: str,
        requested_turn_id: int | None,
    ) -> tuple[str, int | None, Any]:
        resolved_conversation_id = self.resolve_conversation_id(
            user_id=user_id,
            conversation_id=conversation_id,
            resume=resume,
        )

        if not resume and requested_turn_id not in {None, 1}:
            raise ValueError(
                "explicit turn_id > 1 requires resuming an existing conversation"
            )

        if resume:
            state = self.load_state(
                user_id=user_id,
                conversation_id=resolved_conversation_id,
            )
            if state is None:
                raise ValueError(
                    f"cannot resume conversation {resolved_conversation_id}: no saved state found"
                )
            next_turn_id = state.turn_id + 1
            if requested_turn_id is not None and requested_turn_id != next_turn_id:
                raise ValueError(
                    f"turn mismatch for {resolved_conversation_id}: expected {next_turn_id}, got {requested_turn_id}"
                )
            return resolved_conversation_id, next_turn_id, state

        existing_state = self.load_state(
            user_id=user_id,
            conversation_id=resolved_conversation_id,
            strict=False,
        )
        if existing_state is not None:
            next_turn_id = existing_state.turn_id + 1
            return resolved_conversation_id, next_turn_id, existing_state

        title = user_request.strip().splitlines()[0][:80] if user_request.strip() else resolved_conversation_id
        self.registry.ensure_conversation(
            user_id=user_id,
            conversation_id=resolved_conversation_id,
            title=title,
        )
        initial_turn_id = requested_turn_id or 1
        return resolved_conversation_id, initial_turn_id, None

    def save(self, state) -> Path:
        with self._lock:
            path = self.store.save(state)
            self.registry.update_from_state(state)
            return path

    def save_async(self, state) -> Future[Path]:
        def _save() -> Path:
            return self.save(state)

        return self._executor.submit(_save)
