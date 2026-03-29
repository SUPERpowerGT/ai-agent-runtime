from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
import time
from typing import Deque

from runtime.engine import AgentRuntime
from state.state import TaskState


@dataclass
class TaskEnvelope:
    state: TaskState
    enqueued_at: float = field(default_factory=time.time)
    priority: int = 0


class InMemoryTaskScheduler:
    """
    Lightweight runtime scheduler used to model queueing and worker dispatch.

    This keeps the implementation intentionally simple while making queue wait,
    worker admission, and batch execution explicit runtime concepts.
    """

    def __init__(self, *, max_concurrent_tasks: int = 1):
        if max_concurrent_tasks < 1:
            raise ValueError("max_concurrent_tasks must be at least 1")

        self.max_concurrent_tasks = max_concurrent_tasks
        self._queue: Deque[TaskEnvelope] = deque()
        self._active_tasks = 0

    def submit(self, state: TaskState, *, priority: int = 0) -> TaskEnvelope:
        envelope = TaskEnvelope(state=state, priority=priority)
        self._queue.append(envelope)
        return envelope

    def queue_depth(self) -> int:
        return len(self._queue)

    def has_capacity(self) -> bool:
        return self._active_tasks < self.max_concurrent_tasks

    def pop_next(self) -> TaskEnvelope | None:
        if not self._queue or not self.has_capacity():
            return None

        envelope = self._queue.popleft()
        self._active_tasks += 1
        waited_ms = (time.time() - envelope.enqueued_at) * 1000
        envelope.state.record_queue_wait(waited_ms)
        return envelope

    def finish(self) -> None:
        if self._active_tasks > 0:
            self._active_tasks -= 1

    def run_next(self, runtime: AgentRuntime) -> TaskState | None:
        envelope = self.pop_next()
        if envelope is None:
            return None

        try:
            return runtime.run(envelope.state)
        finally:
            self.finish()

