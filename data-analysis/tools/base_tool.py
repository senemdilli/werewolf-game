"""
Basic tool for data analysis.
All tools should inherit from this class and implement the `run` method.
"""

from abc import ABC, abstractmethod
from multiprocessing import get_logger
from typing import ClassVar

class BaseTool(ABC):
    """
    Base class for all tools.
    """

    # Mandatory class variables that must be defined by subclasses
    name: ClassVar[str] = ""
    description: ClassVar[str] = ""

    def __init__(self) -> None:
        """
        Initialize the tool.
        """
        if not self.name:
            raise ValueError("Tool name must be defined.")
        if not self.description:
            raise ValueError("Tool description must be defined.")
        
        self.logger = get_logger(f"tools.{self.name}")

    @abstractmethod
    def run(self, *args, **kwargs):
        """
        Run the tool.
        This method should be implemented by all subclasses.
        """
        pass