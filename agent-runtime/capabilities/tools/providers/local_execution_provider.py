from __future__ import annotations

from dataclasses import dataclass, field

from infrastructure.execution.sandbox.manager import SandboxManager
from infrastructure.execution.sandbox.policy import SandboxPolicy


@dataclass(frozen=True)
class ExecutionPolicy:
    mode: str = "permissive"
    allowed_cwds: tuple[str, ...] = field(default_factory=tuple)
    blocked_commands: tuple[str, ...] = field(default_factory=lambda: ("rm", "sudo"))
    allowed_env_keys: tuple[str, ...] = field(default_factory=tuple)
    timeout_seconds: int = 10
    max_memory_mb: int | None = None
    cpu_time_seconds: int | None = None
    max_processes: int | None = None
    max_file_size_mb: int | None = None
    max_output_bytes: int = 32_768

    def to_sandbox_policy(self) -> SandboxPolicy:
        return SandboxPolicy(
            mode=self.mode,
            timeout_seconds=self.timeout_seconds,
            max_memory_mb=self.max_memory_mb,
            cpu_time_seconds=self.cpu_time_seconds,
            max_processes=self.max_processes,
            max_file_size_mb=self.max_file_size_mb,
            max_output_bytes=self.max_output_bytes,
            allowed_cwds=self.allowed_cwds,
            blocked_commands=self.blocked_commands,
            allowed_env_keys=self.allowed_env_keys,
        )

    def describe(self) -> dict:
        return self.to_sandbox_policy().describe()


class LocalExecutionProvider:
    """
    Minimal local execution backend.

    This is intentionally simple: it establishes the execution contract used by
    the runtime without claiming strong isolation. The provider can later be
    swapped with a real sandbox, container, or remote executor.
    """

    def __init__(self, *, policy: ExecutionPolicy | None = None):
        self.policy = policy or ExecutionPolicy()
        self.manager = SandboxManager(default_policy=self.policy.to_sandbox_policy())

    def execute(
        self,
        *,
        command: list[str],
        cwd: str | None = None,
        timeout_seconds: int = 10,
        env: dict[str, str] | None = None,
        policy_mode: str | None = None,
        allowed_cwds: list[str] | None = None,
        blocked_commands: list[str] | None = None,
        allowed_env_keys: list[str] | None = None,
    ) -> dict:
        result = self.manager.execute(
            command=command,
            cwd=cwd,
            timeout_seconds=timeout_seconds,
            env=env,
            policy_mode=policy_mode,
            allowed_cwds=allowed_cwds,
            blocked_commands=blocked_commands,
            allowed_env_keys=allowed_env_keys,
        )
        payload = result.to_dict()
        payload["timeout_seconds"] = timeout_seconds
        return payload
