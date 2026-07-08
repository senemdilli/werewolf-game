"""Central registry for all tools."""

from base_tool import BaseTool

class ToolRegistry:
    """
    A registry for managing and accessing tools.
    """

    def __init__(self):
        self._tools: dict[str, BaseTool] = {}

    def register_tool(self, tool: BaseTool) -> None:
        """
        Register a new tool in the registry.

        Args:
            tool (BaseTool): The tool instance to register.
        """
        if tool.name in self._tools:
            raise ValueError(f"Tool with name '{tool.name}' is already registered.")
        self._tools[tool.name] = tool

    def get_tool(self, name: str) -> BaseTool:
        """
        Retrieve a tool by its name.

        Args:
            name (str): The name of the tool to retrieve.

        Returns:
            BaseTool: The tool instance associated with the given name.
        """
        if name not in self._tools:
            raise KeyError(f"Tool with name '{name}' is not registered.")
        return self._tools[name]

    def list_tools(self) -> list[str]:
        """
        List all registered tools.

        Returns:
            list[str]: A list of names of all registered tools.
        """
        return sorted(self._tools.keys())
    
tool_registry = ToolRegistry()