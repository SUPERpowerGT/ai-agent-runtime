from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class SkillResult:
    skill_name: str
    data: Any = None
    success: bool = True
    error: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SkillCapability:
    category: str = "general"
    networked: bool = False
    requires_files: bool = False
    read_only: bool = True
    tags: list[str] = field(default_factory=list)


class BaseSkill:
    """
    Base abstraction for globally registered runtime skills.

    A skill is a capability implementation. Agents may request skills, but the
    runtime owns permission checks and execution.
    """

    name: str = ""
    description: str = ""
    input_schema: dict[str, Any] = {}
    capability = SkillCapability()

    def run(self, **kwargs) -> Any:
        raise NotImplementedError

    def execute(self, **kwargs) -> SkillResult:
        try:
            data = self.run(**kwargs)
            metadata = self.build_metadata(data)
            return SkillResult(
                skill_name=self.name,
                data=data,
                success=True,
                metadata=metadata,
            )
        except Exception as exc:
            return SkillResult(
                skill_name=self.name,
                data=None,
                success=False,
                error=str(exc),
                metadata={},
            )

    def build_metadata(self, data: Any) -> dict[str, Any]:
        return {}

    def summarize_output(self, data: Any) -> Any:
        return data

    def summarize_result(self, result: SkillResult) -> dict[str, Any]:
        return {
            "success": result.success,
            "error": result.error,
            "metadata": result.metadata,
            "data": self.summarize_output(result.data),
        }

    def describe(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
            "capability": asdict(self.capability),
        }
