from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class StateReadPolicy:
    """
    Controls how much state an agent is allowed to read into prompt context.
    """

    conversation_message_limit: int = 4
    history_limit: int = 3
    memory_keys: tuple[str, ...] = ()
    memory_max_items: int = 8
    memory_max_chars: int = 800
    local_memory_keys: tuple[str, ...] = ()
    local_memory_max_items: int = 4
    local_memory_max_chars: int = 1200


@dataclass(frozen=True)
class StateReadContext:
    user_request: str
    latest_user_message: str
    current_turn: dict[str, Any]
    conversation_context: str
    history_context: str
    memory_context: str
    local_memory: str

    def to_prompt_fields(self) -> dict[str, Any]:
        return {
            "user_request": self.user_request,
            "latest_user_message": self.latest_user_message,
            "current_turn": self.current_turn,
            "conversation_context": self.conversation_context,
            "conversation_log": self.conversation_context,
            "history_context": self.history_context,
            "memory_context": self.memory_context,
            "local_memory": self.local_memory,
        }
