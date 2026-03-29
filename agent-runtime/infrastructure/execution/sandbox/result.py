from __future__ import annotations

from dataclasses import dataclass

from infrastructure.execution.sandbox.policy import SandboxPolicy


@dataclass(frozen=True)
class SandboxResult:
    command: list[str]
    cwd: str | None
    exit_code: int | None
    timed_out: bool
    duration_ms: float
    stdout: str
    stderr: str
    backend: str
    policy: SandboxPolicy
    error_type: str | None = None
    termination_signal: int | None = None

    def to_dict(self) -> dict:
        return {
            "command": self.command,
            "cwd": self.cwd,
            "exit_code": self.exit_code,
            "timed_out": self.timed_out,
            "duration_ms": round(self.duration_ms, 2),
            "stdout": self.stdout,
            "stderr": self.stderr,
            "backend": self.backend,
            "policy": self.policy.describe(),
            "error_type": self.error_type,
            "termination_signal": self.termination_signal,
        }

