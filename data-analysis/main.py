"""Run an analysis tool from the CLI (debugging aid + reproducible runs).

    uv run python main.py tool compare_data --params '{"filters_a": {"sources": ["human"]}}'
    uv run python main.py tool plot --params '{"filters": {"room_codes": ["5NOHGS"]}, "kind": "histogram"}'
    uv run python main.py tool delta_tool --params '{"filters": {}, "compare": "trust_type", "value_a": "alignment", "value_b": "information"}'
    uv run python main.py tool correlation_tool --params '{"filters_a": {"sources": ["human"]}, "filters_b": {"sources": ["llm"]}}'

Run the analysis agent from the CLI.
    uv run python main.py agent
    or
    make run
"""

import argparse
import json
from pathlib import Path

from core.logging import get_logger
from data.dataset import load_dataset
from agent.orchestrator import OrchestratorConfig, Orchestrator, OrchestratorResponse

def build_tools(game_records: str, llm_results: str, use_ffill: bool = True, full_y_scale: bool = False) -> dict:
    from tools.compare_tool import CompareDataTool
    from tools.correlation_tool import CorrelationTool
    from tools.delta_tool import DeltaTool
    from tools.plot_tool import PlotTool

    df = load_dataset(game_records, llm_results, cache_dir="analysis/cache", use_ffill=use_ffill)
    tools = (CompareDataTool(df), PlotTool(df, plots_dir="analysis/plots", default_full_y_scale=full_y_scale), DeltaTool(df), CorrelationTool(df))
    return {tool.name: tool for tool in tools}


def main() -> None:
    logger = get_logger("main")
    logger.info("Starting analysis tool")
    
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    tool_cmd = sub.add_parser("tool", help="run one analysis tool with JSON params")
    tool_cmd.add_argument("name", help="tool name, e.g. compare_data or plot")
    tool_cmd.add_argument("--params", default="{}", help="JSON object of run() arguments")
    tool_cmd.add_argument("--game-records", default="../results/game-records")
    tool_cmd.add_argument("--llm-results", default="../llm-labeling/results/llm-labeling")
    tool_cmd.add_argument("--raw-human", action="store_true", help="disable forward-fill for human labels (keep raw events)")
    tool_cmd.add_argument("--full-y-scale", action="store_true", help="enforce full Y-axis limits [0, 1] / [1, 7]")

    agent_cmd = sub.add_parser("agent", help="ask the analysis agent a question")
    agent_cmd.add_argument("question", nargs="?", help="natural-language question to ask")
    agent_cmd.add_argument("--game-records", default="../results/game-records")
    agent_cmd.add_argument("--llm-results", default="../llm-labeling/results/llm-labeling")
    agent_cmd.add_argument("--cache-dir", default="analysis/cache")
    agent_cmd.add_argument("--plots-dir", default="analysis/plots")
    agent_cmd.add_argument("--model", default=None, help="chat model name, e.g. openai:gpt-5.4-mini")
    agent_cmd.add_argument("--temperature", type=float, default=None)
    agent_cmd.add_argument("--raw-human", action="store_true", help="disable forward-fill for human labels (keep raw events)")
    agent_cmd.add_argument("--full-y-scale", action="store_true", help="enforce full Y-axis limits [0, 1] / [1, 7]")

    args = parser.parse_args()

    if args.command == "agent":
        run_agent(args)
        return

    tools = build_tools(args.game_records, args.llm_results, use_ffill=not args.raw_human, full_y_scale=args.full_y_scale)
    if args.name not in tools:
        parser.error(f"unknown tool {args.name!r}; available: {sorted(tools)}")

    from data.filters import FilterSpec

    params = json.loads(args.params)
    for key, val in params.items():
        if key.startswith("filters") and isinstance(val, dict):
            params[key] = FilterSpec(**val)

    result = tools[args.name].run(**params)
    print(result.model_dump_json(indent=2, exclude_none=True))


def run_agent(args) -> None:
    config = OrchestratorConfig(
        game_records=args.game_records,
        llm_results=args.llm_results,
        cache_dir=args.cache_dir,
        plots_dir=args.plots_dir,
        model=args.model,
        temperature=args.temperature,
        use_ffill=not args.raw_human,
        full_y_scale=args.full_y_scale,
    )

    orchestrator = Orchestrator(config)

    if args.question:
        print(orchestrator.ask(args.question).answer)
        return

    print("Enter a question and press Enter. Submit an empty line to exit.")
    while True:
        try:
            question = input("> ").strip()
        except EOFError:
            break
        if not question:
            break
        print(orchestrator.ask(question).answer)


if __name__ == "__main__":
    main()
