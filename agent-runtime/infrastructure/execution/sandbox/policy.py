from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class SandboxPolicy:
    """
    Runtime policy for sandboxed execution.

    This policy is backend-agnostic on purpose: local subprocess execution,
    containers, or remote executors can all interpret the same constraints.
    """

    mode: str = "permissive"
    timeout_seconds: int = 10
    max_memory_mb: int | None = None
    cpu_time_seconds: int | None = None
    max_processes: int | None = None
    max_file_size_mb: int | None = None
    max_output_bytes: int = 32_768
    allowed_cwds: tuple[str, ...] = field(default_factory=tuple)
    blocked_commands: tuple[str, ...] = field(default_factory=lambda: ("rm", "sudo"))
    allowed_env_keys: tuple[str, ...] = field(default_factory=tuple)

    def describe(self) -> dict:
        return {
            "mode": self.mode,
            "timeout_seconds": self.timeout_seconds,
            "max_memory_mb": self.max_memory_mb,
            "cpu_time_seconds": self.cpu_time_seconds,
            "max_processes": self.max_processes,
            "max_file_size_mb": self.max_file_size_mb,
            "max_output_bytes": self.max_output_bytes,
            "allowed_cwds": list(self.allowed_cwds),
            "blocked_commands": list(self.blocked_commands),
            "allowed_env_keys": list(self.allowed_env_keys),
        }

