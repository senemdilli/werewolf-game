"""Run an analysis tool from the CLI (debugging aid + reproducible runs).

    uv run python main.py tool compare_data --params '{"filters_a": {"sources": ["human"]}}'
    uv run python main.py tool plot --params '{"filters": {"room_codes": ["5NOHGS"]}, "kind": "histogram"}'
    uv run python main.py tool delta_tool --params '{"filters": {}, "compare": "trust_type", "value_a": "alignment", "value_b": "information"}'
    uv run python main.py tool correlation_tool --params '{"filters_a": {"sources": ["human"]}, "filters_b": {"sources": ["llm"]}}'

The orchestrator (phase 3) will call the same tools programmatically.
"""

import argparse
import json

from data.dataset import load_dataset


def build_tools(game_records: str, llm_results: str) -> dict:
    from tools.compare_tool import CompareDataTool
    from tools.correlation_tool import CorrelationTool
    from tools.delta_tool import DeltaTool
    from tools.plot_tool import PlotTool

    df = load_dataset(game_records, llm_results, cache_dir="analysis/cache")
    tools = (CompareDataTool(df), PlotTool(df), DeltaTool(df), CorrelationTool(df))
    return {tool.name: tool for tool in tools}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    tool_cmd = sub.add_parser("tool", help="run one analysis tool with JSON params")
    tool_cmd.add_argument("name", help="tool name, e.g. compare_data or plot")
    tool_cmd.add_argument("--params", default="{}", help="JSON object of run() arguments")
    tool_cmd.add_argument("--game-records", default="../results/game-records")
    tool_cmd.add_argument("--llm-results", default="../llm-labeling/results/llm-labeling")
    args = parser.parse_args()

    tools = build_tools(args.game_records, args.llm_results)
    if args.name not in tools:
        parser.error(f"unknown tool {args.name!r}; available: {sorted(tools)}")

    from data.filters import FilterSpec

    params = json.loads(args.params)
    for key, val in params.items():
        if key.startswith("filters") and isinstance(val, dict):
            params[key] = FilterSpec(**val)

    result = tools[args.name].run(**params)
    print(result.model_dump_json(indent=2, exclude_none=True))


if __name__ == "__main__":
    main()
