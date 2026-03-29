from __future__ import annotations

import os
from dataclasses import replace

from infrastructure.execution.sandbox.backends.local import LocalSandboxBackend
from infrastructure.execution.sandbox.policy import SandboxPolicy
from infrastructure.execution.sandbox.result import SandboxResult


class SandboxManager:
    """
    Coordinates sandbox execution policy, env filtering, and backend dispatch.
    """

    def __init__(
        self,
        *,
        backend=None,
        default_policy: SandboxPolicy | None = None,
    ):
        self.backend = backend or LocalSandboxBackend()
        self.default_policy = default_policy or SandboxPolicy()

    def execute(
        self,
        *,
        command: list[str],
        cwd: str | None = None,
        timeout_seconds: int | None = None,
        env: dict[str, str] | None = None,
        policy_mode: str | None = None,
        allowed_cwds: list[str] | None = None,
        blocked_commands: list[str] | None = None,
        allowed_env_keys: list[str] | None = None,
        max_memory_mb: int | None = None,
        cpu_time_seconds: int | None = None,
        max_processes: int | None = None,
        max_file_size_mb: int | None = None,
        max_output_bytes: int | None = None,
    ) -> SandboxResult:
        policy = self._resolve_policy(
            timeout_seconds=timeout_seconds,
            policy_mode=policy_mode,
            allowed_cwds=allowed_cwds,
            blocked_commands=blocked_commands,
            allowed_env_keys=allowed_env_keys,
            max_memory_mb=max_memory_mb,
            cpu_time_seconds=cpu_time_seconds,
            max_processes=max_processes,
            max_file_size_mb=max_file_size_mb,
            max_output_bytes=max_output_bytes,
        )
        merged_env = os.environ.copy()
        filtered_env = self._filter_env(env or {}, policy)
        if filtered_env:
            merged_env.update(filtered_env)
        return self.backend.execute(
            command=command,
            cwd=cwd,
            env=merged_env,
            policy=policy,
        )

    def _resolve_policy(
        self,
        *,
        timeout_seconds: int | None,
        policy_mode: str | None,
        allowed_cwds: list[str] | None,
        blocked_commands: list[str] | None,
        allowed_env_keys: list[str] | None,
        max_memory_mb: int | None,
        cpu_time_seconds: int | None,
        max_processes: int | None,
        max_file_size_mb: int | None,
        max_output_bytes: int | None,
    ) -> SandboxPolicy:
        return replace(
            self.default_policy,
            timeout_seconds=timeout_seconds or self.default_policy.timeout_seconds,
            mode=policy_mode or self.default_policy.mode,
            allowed_cwds=tuple(allowed_cwds) if allowed_cwds is not None else self.default_policy.allowed_cwds,
            blocked_commands=tuple(blocked_commands) if blocked_commands is not None else self.default_policy.blocked_commands,
            allowed_env_keys=tuple(allowed_env_keys) if allowed_env_keys is not None else self.default_policy.allowed_env_keys,
            max_memory_mb=max_memory_mb if max_memory_mb is not None else self.default_policy.max_memory_mb,
            cpu_time_seconds=cpu_time_seconds if cpu_time_seconds is not None else self.default_policy.cpu_time_seconds,
            max_processes=max_processes if max_processes is not None else self.default_policy.max_processes,
            max_file_size_mb=max_file_size_mb if max_file_size_mb is not None else self.default_policy.max_file_size_mb,
            max_output_bytes=max_output_bytes if max_output_bytes is not None else self.default_policy.max_output_bytes,
        )

    def _filter_env(
        self,
        env: dict[str, str],
        policy: SandboxPolicy,
    ) -> dict[str, str]:
        if not env:
            return {}

        if policy.mode != "restricted" or not policy.allowed_env_keys:
            return dict(env)

        allowed_keys = set(policy.allowed_env_keys)
        filtered_env = {
            key: value
            for key, value in env.items()
            if key in allowed_keys
        }
        dropped_keys = sorted(set(env) - allowed_keys)
        if dropped_keys:
            raise ValueError(
                "environment keys blocked by sandbox policy: "
                + ", ".join(dropped_keys)
            )
        return filtered_env
