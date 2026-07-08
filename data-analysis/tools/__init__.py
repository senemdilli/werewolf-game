"""
Tools for data analysis.
All tools should inherit from the BaseTool class and implement the `run` method.
Register tools here to make them available for use by the orchestrator.
"""

from base_tool import BaseTool
from compare_tool import CompareDataTool
from correlation_tool import CorrelationTool
from delta_tool import DeltaTool
from plot_tool import PlotTool
from registry import tool_registry

__all__ = ["BaseTool", "tool_registry"]

tool_registry.register_tool(CompareDataTool())
tool_registry.register_tool(CorrelationTool())
tool_registry.register_tool(DeltaTool())
tool_registry.register_tool(PlotTool())

__all__ += ["CompareDataTool", "CorrelationTool", "DeltaTool", "PlotTool"]