from __future__ import annotations

from capabilities.skills.registry import SkillRegistry


class SkillManager:
    """
    Runtime-facing coordinator for global skill access and authorization.
    """

    def __init__(self, registry: SkillRegistry):
        self.registry = registry

    def list_skills(self) -> list[str]:
        return self.registry.list_skills()

    def describe_skill(self, name: str) -> dict:
        return self.registry.describe_skill(name)

    def agent_can_use(self, agent, skill_name: str) -> bool:
        allowed = getattr(agent, "allowed_skills", None)
        if allowed:
            return skill_name in allowed

        return True

    def execute_skill(
        self,
        *,
        state,
        agent,
        skill_name: str,
        skill_input: dict | None = None,
    ):
        if not self.agent_can_use(agent, skill_name):
            raise PermissionError(
                f"agent '{agent.name}' is not allowed to use skill '{skill_name}'"
            )

        skill_input = skill_input or {}
        result = self.registry.execute(skill_name=skill_name, **skill_input)

        state.add_tool_call(
            agent_name=agent.name,
            tool_name=skill_name,
            tool_input=skill_input,
            tool_output=self.registry.get(skill_name).summarize_result(result),
            success=result.success,
            error=result.error,
        )

        if skill_name == "sandbox_execute":
            duration_ms = 0.0
            execution_success = result.success
            if isinstance(result.data, dict):
                duration_ms = float(result.data.get("duration_ms", 0.0) or 0.0)
                timed_out = bool(result.data.get("timed_out", False))
                exit_code = result.data.get("exit_code")
                execution_success = result.success and (not timed_out) and exit_code == 0
            state.record_execution_call(duration_ms, success=execution_success)

        if not result.success:
            raise ValueError(result.error or f"{skill_name} failed")

        return result.data
