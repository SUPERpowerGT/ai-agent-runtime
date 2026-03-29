from __future__ import annotations

from capabilities.skills.base_skill import BaseSkill, SkillCapability, SkillResult
from capabilities.tools.base_tool import BaseTool


class ToolBackedSkill(BaseSkill):
    """
    Adapter that exposes an existing tool through the global skill layer.
    """

    def __init__(self, tool: BaseTool):
        self.tool = tool
        self.name = tool.name
        self.description = tool.description
        self.input_schema = tool.input_schema
        self.capability = SkillCapability(
            category=tool.capability.category,
            networked=tool.capability.networked,
            requires_files=tool.capability.requires_files,
            read_only=tool.capability.read_only,
            tags=list(tool.capability.tags),
        )

    def run(self, **kwargs):
        return self.tool.run(**kwargs)

    def execute(self, **kwargs) -> SkillResult:
        result = self.tool.execute(**kwargs)
        return SkillResult(
            skill_name=self.name,
            data=result.data,
            success=result.success,
            error=result.error,
            metadata=result.metadata,
        )

    def build_metadata(self, data):
        return self.tool.build_metadata(data)

    def summarize_output(self, data):
        return self.tool.summarize_output(data)
