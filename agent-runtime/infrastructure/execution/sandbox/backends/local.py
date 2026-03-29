from __future__ import annotations

import os
import signal
import subprocess
import time

from infrastructure.execution.sandbox.policy import SandboxPolicy
from infrastructure.execution.sandbox.result import SandboxResult

try:
    import resource
except ImportError:  # pragma: no cover - non-POSIX fallback
    resource = None


class LocalSandboxBackend:
    """
    Local subprocess backend with sandbox-style controls.

    This is not a strong isolation boundary, but it centralizes timeout,
    policy validation, error capture, and basic resource limits behind the
    same contract future backends can implement.
    """

    name = "local"

    def execute(
        self,
        *,
        command: list[str],
        cwd: str | None,
        env: dict[str, str],
        policy: SandboxPolicy,
    ) -> SandboxResult:
        self._validate_command(command, cwd, policy)

        start = time.perf_counter()
        process = subprocess.Popen(
            command,
            cwd=cwd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            preexec_fn=self._build_preexec_fn(policy) if os.name != "nt" else None,
        )

        try:
            stdout, stderr = process.communicate(timeout=policy.timeout_seconds)
            duration_ms = (time.perf_counter() - start) * 1000
            exit_code = process.returncode
            termination_signal = -exit_code if exit_code is not None and exit_code < 0 else None
            error_type = self._classify_error(exit_code=exit_code, timed_out=False)
            return SandboxResult(
                command=command,
                cwd=cwd,
                exit_code=exit_code,
                timed_out=False,
                duration_ms=duration_ms,
                stdout=self._trim_output(stdout, policy),
                stderr=self._trim_output(stderr, policy),
                backend=self.name,
                policy=policy,
                error_type=error_type,
                termination_signal=termination_signal,
            )
        except subprocess.TimeoutExpired:
            process.kill()
            stdout, stderr = process.communicate()
            duration_ms = (time.perf_counter() - start) * 1000
            return SandboxResult(
                command=command,
                cwd=cwd,
                exit_code=None,
                timed_out=True,
                duration_ms=duration_ms,
                stdout=self._trim_output(stdout or "", policy),
                stderr=self._trim_output((stderr or "") + "\nprocess exceeded timeout", policy),
                backend=self.name,
                policy=policy,
                error_type="timeout",
            )

    def _validate_command(
        self,
        command: list[str],
        cwd: str | None,
        policy: SandboxPolicy,
    ) -> None:
        if not command:
            raise ValueError("sandbox execution requires a non-empty command")

        executable = command[0]
        blocked = set(policy.blocked_commands)
        if executable in blocked:
            raise ValueError(f"command '{executable}' is blocked by sandbox policy")

        if policy.mode != "restricted":
            return

        if cwd and policy.allowed_cwds:
            normalized_cwd = os.path.abspath(cwd)
            allowed = [os.path.abspath(path) for path in policy.allowed_cwds]
            if not any(
                normalized_cwd == allowed_cwd
                or normalized_cwd.startswith(f"{allowed_cwd}{os.sep}")
                for allowed_cwd in allowed
            ):
                raise ValueError(f"cwd '{cwd}' is not allowed by restricted sandbox policy")

    def _build_preexec_fn(self, policy: SandboxPolicy):
        if resource is None:
            return None

        def _apply_limits():
            if policy.max_memory_mb:
                limit = policy.max_memory_mb * 1024 * 1024
                resource.setrlimit(resource.RLIMIT_AS, (limit, limit))
            if policy.cpu_time_seconds:
                resource.setrlimit(
                    resource.RLIMIT_CPU,
                    (policy.cpu_time_seconds, policy.cpu_time_seconds),
                )
            if policy.max_processes:
                resource.setrlimit(
                    resource.RLIMIT_NPROC,
                    (policy.max_processes, policy.max_processes),
                )
            if policy.max_file_size_mb:
                limit = policy.max_file_size_mb * 1024 * 1024
                resource.setrlimit(resource.RLIMIT_FSIZE, (limit, limit))

        return _apply_limits

    def _trim_output(self, content: str, policy: SandboxPolicy) -> str:
        if len(content) <= policy.max_output_bytes:
            return content
        truncated = content[: policy.max_output_bytes]
        return truncated + "\n...[truncated by sandbox output limit]"

    def _classify_error(self, *, exit_code: int | None, timed_out: bool) -> str | None:
        if timed_out:
            return "timeout"
        if exit_code is None or exit_code == 0:
            return None
        if exit_code < 0:
            signum = -exit_code
            if signum == signal.SIGKILL:
                return "killed"
            if signum == signal.SIGXCPU:
                return "cpu_limit"
            return "signal"
        return "runtime_error"

