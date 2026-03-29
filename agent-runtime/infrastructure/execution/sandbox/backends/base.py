from __future__ import annotations

from typing import Protocol

from infrastructure.execution.sandbox.policy import SandboxPolicy
from infrastructure.execution.sandbox.result import SandboxResult


class SandboxBackend(Protocol):
    name: str

    def execute(
        self,
        *,
        command: list[str],
        cwd: str | None,
        env: dict[str, str],
        policy: SandboxPolicy,
    ) -> SandboxResult: ...
