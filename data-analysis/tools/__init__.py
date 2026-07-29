"""
Tools for data analysis.
All tools should inherit from the BaseTool class and implement the `run` method.
Register tools here to make them available for use by the orchestrator.
"""

from pathlib import Path

from .base_tool import BaseTool
from .compare_tool import CompareDataTool
from .correlation_tool import CorrelationTool
from .delta_tool import DeltaTool
from .plot_tool import PlotTool
from .registry import ToolRegistry, tool_registry

__all__ = [
	"BaseTool",
	"ToolRegistry",
	"tool_registry",
	"CompareDataTool",
	"CorrelationTool",
	"DeltaTool",
	"PlotTool",
	"build_analysis_tools",
]


def build_analysis_tools(df, plots_dir: str | Path = "../results/data-analysis/plots") -> dict[str, BaseTool]:
	tools = (
		CompareDataTool(df),
		PlotTool(df, plots_dir=plots_dir),
		DeltaTool(df),
		CorrelationTool(df),
	)
	return {tool.name: tool for tool in tools}