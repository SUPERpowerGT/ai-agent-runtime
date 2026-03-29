from __future__ import annotations

import json
from pathlib import Path
from threading import Lock
from concurrent.futures import Future, ThreadPoolExecutor

from state.state import TaskState


class SessionStore:
    """
    Lightweight file-backed session store for single-user CLI conversation flows.
    """

    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()
        self._executor = ThreadPoolExecutor(
            max_workers=1,
            thread_name_prefix="session-store",
        )

    def session_path(self, conversation_id: str) -> Path:
        return self.root / f"{conversation_id}.json"

    def exists(self, conversation_id: str) -> bool:
        return self.session_path(conversation_id).exists()

    def load(self, conversation_id: str) -> TaskState:
        with self._lock:
            payload = json.loads(self.session_path(conversation_id).read_text(encoding="utf-8"))
        return TaskState.from_snapshot(payload)

    def save(self, state: TaskState) -> Path:
        path = self.session_path(state.conversation_id)
        payload = json.dumps(state.to_snapshot(), ensure_ascii=False, indent=2)
        with self._lock:
            path.write_text(payload, encoding="utf-8")
        return path

    def save_async(self, state: TaskState) -> Future[Path]:
        snapshot = state.to_snapshot()
        conversation_id = state.conversation_id

        def _write() -> Path:
            path = self.session_path(conversation_id)
            payload = json.dumps(snapshot, ensure_ascii=False, indent=2)
            with self._lock:
                path.write_text(payload, encoding="utf-8")
            return path

        return self._executor.submit(_write)
