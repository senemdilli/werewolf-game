import argparse
import glob
import json
import os
import sys
from pathlib import Path

src_dir = Path(__file__).parents[1]
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

from wolf_llm_labeling.runner import run_labeling_experiment

def main():
    parser = argparse.ArgumentParser(description="Batch Runner")
    parser.add_argument("--config", type=str, help="Path to config JSON")
    parser.add_argument("--primary-model", type=str, default="gemma4:26b")
    parser.add_argument("--inner-voice-model", type=str)
    parser.add_argument("--ollama-url", type=str, default="https://gpu.snet.tu-berlin.de/echelon/ollama")
    parser.add_argument("--game-dir", type=str, default="./results/game-records")
    parser.add_argument("--output-dir", type=str, default="./results/llm-labeling")
    parser.add_argument("--formatter", type=str, default="markdown")
    parser.add_argument("--context-as-tool", action="store_true")
    parser.add_argument("--runs", type=int, default=1, help="Number of times to repeat each run (default: 1)")
    parser.add_argument("--chronology", type=str, default="numeric", choices=["numeric", "timestamp"], help="Chronology formatting type")
    parser.add_argument("--list-style", type=str, default="plain", choices=["plain", "dash"], help="Enumeration style for Static Data / Current Game State lines")
    
    args = parser.parse_args()
    
    if args.config:
        with open(args.config, "r", encoding="utf-8") as f:
            config = json.load(f)
            
        url = config.get("ollama_url", args.ollama_url)
        model = config.get("primary_model", args.primary_model)
        iv_model = config.get("inner_voice_model", args.inner_voice_model)
        out_dir = config.get("output_dir", args.output_dir)
        fmt = config.get("formatter", args.formatter)
        ctx_tool = config.get("context_as_tool", args.context_as_tool)
        default_runs_count = config.get("runs_count", config.get("repeat", args.runs))
        chrono = config.get("chronology", args.chronology)
        style = config.get("list_style", args.list_style)
        
        for run in config.get("runs", []):
            game_pattern = run.get("game_pattern", "game-*.csv")
            game_dir_path = Path(args.game_dir)
            csv_files = glob.glob(str(game_dir_path / game_pattern))
            run_runs_count = run.get("runs_count", run.get("repeat", default_runs_count))
            run_chrono = run.get("chronology", chrono)
            run_style = run.get("list_style", style)
            
            for csv_path in csv_files:
                json_path = csv_path.replace(".csv", "-labels.json")
                if not os.path.exists(json_path):
                    continue
                
                for r_idx in range(run_runs_count):
                    if run_runs_count > 1:
                        print(f"[{csv_path}] Run {r_idx + 1} of {run_runs_count}...")
                    try:
                        run_labeling_experiment(
                            game_record_json=json_path,
                            game_record_csv=csv_path,
                            primary_model=model,
                            inner_voice_model=iv_model,
                            ollama_url=url,
                            experiment=run["experiment"],
                            experiment_args=run.get("args", ""),
                            output_dir=out_dir,
                            formatter=run.get("formatter", fmt),
                            context_as_tool=run.get("context_as_tool", ctx_tool),
                            chronology=run_chrono,
                            list_style_mode=run_style,
                        )
                    except Exception as e:
                        print(f"Error in batch run for {csv_path} (iteration {r_idx + 1}): {e}", file=sys.stderr)
    else:
        game_dir_path = Path(args.game_dir)
        csv_files = glob.glob(str(game_dir_path / "game-*.csv"))
        
        experiments = [
            {"experiment": "a", "args": "3"},
            {"experiment": "d", "args": "3 2"},
        ]
        
        for csv_path in csv_files:
            json_path = csv_path.replace(".csv", "-labels.json")
            if not os.path.exists(json_path):
                continue
                
            for exp in experiments:
                for r_idx in range(args.runs):
                    if args.runs > 1:
                        print(f"[{csv_path}] Experiment {exp['experiment']} - Run {r_idx + 1} of {args.runs}...")
                    try:
                        run_labeling_experiment(
                            game_record_json=json_path,
                            game_record_csv=csv_path,
                            primary_model=args.primary_model,
                            inner_voice_model=args.inner_voice_model,
                            ollama_url=args.ollama_url,
                            experiment=exp["experiment"],
                            experiment_args=exp["args"],
                            output_dir=args.output_dir,
                            formatter=args.formatter,
                            context_as_tool=args.context_as_tool,
                            chronology=args.chronology,
                            list_style_mode=args.list_style,
                        )
                    except Exception as e:
                        print(f"Error in default batch run for {csv_path}: {e}", file=sys.stderr)

if __name__ == "__main__":
    main()
