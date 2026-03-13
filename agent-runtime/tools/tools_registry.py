class ToolRegistry:
    """
    统一管理系统中的所有工具
    """

    def __init__(self):
        self.tools = {}

    def register(self, tool):
        """
        注册一个工具
        """
        self.tools[tool.name] = tool

    def get(self, name):
        """
        根据名字获取工具
        """
        if name not in self.tools:
            raise ValueError(f"Tool '{name}' not found")

        return self.tools[name]

    def list_tools(self):
        """
        返回当前系统所有工具
        """
        return list(self.tools.keys())