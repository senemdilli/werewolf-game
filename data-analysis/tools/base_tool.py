"""
Basic tool for data analysis.
All tools should inherit from this class and implement the `run` method.
"""

import functools
import inspect

from abc import ABC, abstractmethod
from typing import Any, ClassVar
from pydantic import BaseModel

from core.logging import get_logger

from langchain_core.tools import StructuredTool

from contracts.tool_output import ToolOutput

class BaseTool(ABC):
    """
    Base class for all tools.
    """

    # Mandatory class variables that must be defined by subclasses
    name: ClassVar[str] = ""
    description: ClassVar[str] = ""

    # Optional class variables for input/output schemas
    input_schema: ClassVar[type[BaseModel] | None] = None
    output_schema: ClassVar[type[BaseModel] | None] = None

    def __init__(self) -> None:
        """
        Initialize the tool.
        """
        if not self.name:
            raise ValueError("Tool name must be defined.")
        if not self.description:
            raise ValueError("Tool description must be defined.")
        
        self.logger = get_logger(f"tools.{self.name}")
        self.logger.debug("Initialized tool: %s", self.name)


    @abstractmethod
    def run(self, **kwargs: Any) -> ToolOutput:
        """
        Run the tool.
        This method should be implemented by all subclasses.
        """
        ...

    def as_langchain_tool(self) -> StructuredTool:
        """
        Convert the tool to a LangChain tool.
        Returns a StructuredTool that can be used in LangChain pipelines.
        """

        @functools.wraps(self.run)
        def invoke(**call_kwargs: Any) -> ToolOutput:
            result = self.run(**call_kwargs)
            if not result.success:
                self.logger.error(f"Tool {self.name} failed with error: {result.error}")
            return result
        
        invoke.__signature__ = inspect.signature(self.run)
        
        kwargs: dict[str, Any] = {
            "name": self.name,
            "description": self.description,
            "func": invoke,
        }

        return StructuredTool.from_function(**kwargs)

    def __repr__(self) -> str:
        return f"<Tool name={self.name}>"
