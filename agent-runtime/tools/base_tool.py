from typing import Dict, Any

class BaseTool:
    """
    所有工具的基础类
    """

    name: str = ""
    description: str = ""
    input_schema: Dict = {}

    def run(self, **kwargs) -> Any:
        raise NotImplementedError