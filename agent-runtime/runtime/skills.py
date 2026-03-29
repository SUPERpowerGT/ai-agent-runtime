from __future__ import annotations

from capabilities.skills.manager import SkillManager
from capabilities.skills.registry import SkillRegistry
from capabilities.skills.tool_skill import ToolBackedSkill
from runtime.tools import init_tools


def build_skill_registry(*, tool_registry=None) -> SkillRegistry:
    tool_registry = tool_registry or init_tools()
    registry = SkillRegistry()

    for tool_name in tool_registry.list_tools():
        registry.register(ToolBackedSkill(tool_registry.get(tool_name)))

    return registry


def build_skill_manager(*, skill_registry=None, tool_registry=None) -> SkillManager:
    registry = skill_registry or build_skill_registry(tool_registry=tool_registry)
    return SkillManager(registry)
