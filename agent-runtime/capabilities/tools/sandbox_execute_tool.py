from __future__ import annotations

from capabilities.tools.base_tool import BaseTool, ToolCapability
from capabilities.tools.providers.mcp import MCPSandboxExecuteProvider
from observability.logging import log_tool


class SandboxExecuteTool(BaseTool):
    name = "sandbox_execute"
    description = (
        "Execute a command through an MCP-backed execution interface."
    )
    capability = ToolCapability(
        category="execution",
        networked=True,
        requires_files=False,
        read_only=False,
        tags=["execution", "sandbox", "mcp"],
    )
    input_schema = {
        "type": "object",
        "properties": {
            "command": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Executable command as argv tokens",
            },
            "cwd": {
                "type": "string",
                "description": "Working directory for the command",
            },
            "timeout_seconds": {
                "type": "integer",
                "description": "Maximum execution time before timeout",
            },
            "env": {
                "type": "object",
                "description": "Optional environment variable overrides",
            },
            "policy_mode": {
                "type": "string",
                "description": "Execution policy mode: permissive or restricted",
            },
            "allowed_cwds": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Allowed working directories when policy_mode is restricted",
            },
            "blocked_commands": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Commands denied by policy before execution",
            },
            "allowed_env_keys": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Environment keys allowed when policy_mode is restricted",
            },
        },
        "required": ["command"],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "command": {"type": "array"},
            "cwd": {"type": "string"},
            "exit_code": {"type": "integer"},
            "timed_out": {"type": "boolean"},
            "duration_ms": {"type": "number"},
            "stdout": {"type": "string"},
            "stderr": {"type": "string"},
            "backend": {"type": "string"},
            "error_type": {"type": "string"},
            "termination_signal": {"type": "integer"},
            "policy": {"type": "object"},
        },
        "required": ["timed_out", "duration_ms", "policy", "backend"],
    }
    execution = {"taskSupport": "optional"}

    def __init__(self, provider=None, timeout_seconds: int = 10):
        self.provider = provider or MCPSandboxExecuteProvider()
        self.timeout_seconds = timeout_seconds

    def run(self, **kwargs) -> dict:
        command = kwargs.get("command")
        cwd = kwargs.get("cwd")
        timeout_seconds = kwargs.get("timeout_seconds", self.timeout_seconds)
        env = kwargs.get("env")
        policy_mode = kwargs.get("policy_mode")
        allowed_cwds = kwargs.get("allowed_cwds")
        blocked_commands = kwargs.get("blocked_commands")
        allowed_env_keys = kwargs.get("allowed_env_keys")

        if not command:
            raise ValueError("sandbox_execute requires 'command' parameter")
        if not isinstance(command, list) or not all(isinstance(part, str) for part in command):
            raise ValueError("sandbox_execute 'command' must be a list of strings")

        transport = self._provider_transport()
        log_tool(
            self.name,
            f"transport={transport} executing command: {' '.join(command)}",
        )

        result = self.provider.execute(
            command=command,
            cwd=cwd,
            timeout_seconds=timeout_seconds,
            env=env,
            policy_mode=policy_mode,
            allowed_cwds=allowed_cwds,
            blocked_commands=blocked_commands,
            allowed_env_keys=allowed_env_keys,
        )

        status = "timeout" if result.get("timed_out") else f"exit_code={result.get('exit_code')}"
        log_tool(self.name, f"{status} duration_ms={result.get('duration_ms')}")

        return result

    def build_metadata(self, data: dict) -> dict:
        if not isinstance(data, dict):
            return {}
        metadata = {
            "exit_code": data.get("exit_code"),
            "timed_out": data.get("timed_out", False),
            "duration_ms": data.get("duration_ms", 0),
            "backend": data.get("backend", "unknown"),
            "error_type": data.get("error_type"),
            "termination_signal": data.get("termination_signal"),
            "policy": data.get("policy", {}),
        }
        metadata.update(self._provider_metadata())
        return metadata

    def summarize_output(self, data):
        if not isinstance(data, dict):
            return data
        return {
            "command": data.get("command"),
            "cwd": data.get("cwd"),
            "exit_code": data.get("exit_code"),
            "timed_out": data.get("timed_out", False),
            "duration_ms": data.get("duration_ms", 0),
            "backend": data.get("backend", "unknown"),
            "error_type": data.get("error_type"),
            "termination_signal": data.get("termination_signal"),
            "policy": data.get("policy", {}),
            "stdout": (data.get("stdout") or "")[:500],
            "stderr": (data.get("stderr") or "")[:500],
        }

    def _provider_metadata(self) -> dict:
        if hasattr(self.provider, "describe_transport"):
            return self.provider.describe_transport()
        return {"transport": "unknown"}

    def _provider_transport(self) -> str:
        return self._provider_metadata().get("transport", "unknown")
