from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import ClassVar, Dict, Any


@dataclass
class ToolResult:
    tool_name: str
    data: Any = None
    success: bool = True
    error: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ToolCapability:
    category: str = "general"
    networked: bool = False
    requires_files: bool = False
    read_only: bool = True
    tags: list[str] = field(default_factory=list)


class BaseTool:
    """
    所有工具的基础类
    """

    name: str = ""
    description: str = ""
    input_schema: Dict = {}
    output_schema: Dict = {}
    execution: ClassVar[Dict[str, Any]] = {}
    capability = ToolCapability()

    def run(self, **kwargs) -> Any:
        raise NotImplementedError

    def execute(self, **kwargs) -> ToolResult:
        try:
            data = self.run(**kwargs)
            metadata = self.build_metadata(data)
            return ToolResult(
                tool_name=self.name,
                data=data,
                success=True,
                metadata=metadata,
            )
        except Exception as exc:
            return ToolResult(
                tool_name=self.name,
                data=None,
                success=False,
                error=str(exc),
                metadata={},
            )

    def build_metadata(self, data: Any) -> Dict[str, Any]:
        return {}

    def summarize_output(self, data: Any) -> Any:
        return data

    def summarize_result(self, result: ToolResult) -> Dict[str, Any]:
        return {
            "success": result.success,
            "error": result.error,
            "metadata": result.metadata,
            "data": self.summarize_output(result.data),
        }

    def unwrap_result(self, result: ToolResult) -> Any:
        if not result.success:
            raise ValueError(result.error or f"{self.name} failed")
        return result.data

    def run_or_raise(self, **kwargs) -> Any:
        result = self.execute(**kwargs)
        return self.unwrap_result(result)

    def __call__(self, **kwargs) -> Any:
        return self.run_or_raise(**kwargs)

    def describe(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
            "output_schema": self.output_schema,
            "capability": asdict(self.capability),
        }

    @classmethod
    def describe_mcp_tool(cls) -> Dict[str, Any]:
        return {
            "name": cls.name,
            "description": cls.description,
            "inputSchema": cls.input_schema,
            "outputSchema": cls.output_schema,
            "annotations": cls.mcp_annotations(),
            "execution": cls.execution,
        }

    @classmethod
    def mcp_annotations(cls) -> Dict[str, Any]:
        capability = cls.capability
        return {
            "readOnlyHint": capability.read_only,
            "destructiveHint": not capability.read_only,
            "idempotentHint": capability.read_only,
            "openWorldHint": capability.networked,
        }
