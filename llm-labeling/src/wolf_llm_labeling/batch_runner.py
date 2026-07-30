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
    parser.add_argument("--player-name", type=str, help="Specific player to evaluate (evaluates all if omitted)")
    parser.add_argument("--game-dir", type=str, default="../results/game-records")
    parser.add_argument("--output-dir", type=str, default="../results/llm-labeling")
    parser.add_argument("--prompt-set", type=str, help="Path to prompt set JSON configuration")
    parser.add_argument("--prompt-dir", type=str, default="./prompts")
    parser.add_argument("--formatter", type=str, default="markdown")
    parser.add_argument("--context-as-tool", action="store_true")
    parser.add_argument("--cutoff", type=int, default=3, help="Context cutoff (number of phases back)")
    parser.add_argument("--variant", type=int, default=2, help="Inner voice variant (1: pre-injected, 2: tool loop)")
    parser.add_argument("--inner-voice-type", type=str, default="llm", help="Inner voice type (llm, human, random, constant)")
    parser.add_argument("--max-phases", type=int, default=0, help="Max phases to evaluate (0 for all)")
    parser.add_argument("--temperature", type=float, default=0.0, help="LLM generation temperature")
    parser.add_argument("--use-numeric", action="store_true", help="Force numeric trust scale")
    parser.add_argument("--likert-type", type=str, default="agree-disagree", choices=["agree-disagree", "legacy"])
    parser.add_argument("--parallel", type=int, nargs="?", const=2, default=None, help="Number of parallel threads for player labeling")
    parser.add_argument("--runs", type=int, default=1, help="Number of times to repeat each run (default: 1)")
    parser.add_argument("--chronology", type=str, default="numeric", choices=["numeric", "timestamp"], help="Chronology formatting type")
    
    args = parser.parse_args()
    
    if args.config:
        with open(args.config, "r", encoding="utf-8") as f:
            config = json.load(f)
            
        url = config.get("ollama_url", args.ollama_url)
        model = config.get("primary_model", args.primary_model)
        iv_model = config.get("inner_voice_model", args.inner_voice_model)
        pname = config.get("player_name", args.player_name)
        out_dir = config.get("output_dir", args.output_dir)
        game_dir = config.get("game_dir", args.game_dir)
        pset = config.get("prompt_set", args.prompt_set)
        pdir = config.get("prompt_dir", args.prompt_dir)
        fmt = config.get("formatter", args.formatter)
        ctx_tool = config.get("context_as_tool", args.context_as_tool)
        def_cutoff = config.get("cutoff", args.cutoff)
        def_variant = config.get("variant", args.variant)
        def_iv_type = config.get("inner_voice_type", args.inner_voice_type)
        m_phases = config.get("max_phases", args.max_phases)
        temp = config.get("temperature", args.temperature)
        u_num = config.get("use_numeric", args.use_numeric)
        l_type = config.get("likert_type", args.likert_type)
        par = config.get("parallel", args.parallel)
        default_runs_count = config.get("runs_count", config.get("repeat", args.runs))
        chrono = config.get("chronology", args.chronology)
        
        for run in config.get("runs", []):
            game_pattern = run.get("game_pattern", "game-*.csv")
            game_dir_path = Path(run.get("game_dir", game_dir))
            csv_files = glob.glob(str(game_dir_path / game_pattern))
            run_runs_count = run.get("runs_count", run.get("repeat", default_runs_count))
            run_chrono = run.get("chronology", chrono)
            
            # Construct experiment_args from cutoff, variant, inner_voice_type if legacy "args" not present
            if "args" in run:
                exp_args = run["args"]
            else:
                c_val = run.get("cutoff", def_cutoff)
                v_val = run.get("variant", def_variant)
                iv_val = run.get("inner_voice_type", def_iv_type)
                exp_args = f"{c_val} {v_val} {iv_val}"
            
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
                            primary_model=run.get("primary_model", model),
                            inner_voice_model=run.get("inner_voice_model", iv_model),
                            ollama_url=url,
                            player_name=run.get("player_name", pname),
                            experiment=run["experiment"],
                            experiment_args=exp_args,
                            output_dir=out_dir,
                            max_phases=run.get("max_phases", m_phases),
                            prompt_set_path=run.get("prompt_set", pset),
                            prompt_dir=run.get("prompt_dir", pdir),
                            formatter=run.get("formatter", fmt),
                            context_as_tool=run.get("context_as_tool", ctx_tool),
                            temperature=run.get("temperature", temp),
                            use_likert=(not run.get("use_numeric", u_num)),
                            likert_type=run.get("likert_type", l_type),
                            chronology=run_chrono,
                            parallel=run.get("parallel", par),
                        )
                    except Exception as e:
                        print(f"Error in batch run for {csv_path} (iteration {r_idx + 1}): {e}", file=sys.stderr)
    else:
        game_dir_path = Path(args.game_dir)
        csv_files = glob.glob(str(game_dir_path / "game-*.csv"))
        
        experiments = [
            {"experiment": "a", "cutoff": args.cutoff},
            {"experiment": "d", "cutoff": args.cutoff, "variant": args.variant, "inner_voice_type": args.inner_voice_type},
        ]
        
        for csv_path in csv_files:
            json_path = csv_path.replace(".csv", "-labels.json")
            if not os.path.exists(json_path):
                continue
                
            for exp in experiments:
                c_val = exp.get("cutoff", args.cutoff)
                v_val = exp.get("variant", args.variant)
                iv_val = exp.get("inner_voice_type", args.inner_voice_type)
                exp_args = f"{c_val} {v_val} {iv_val}"

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
                            player_name=args.player_name,
                            experiment=exp["experiment"],
                            experiment_args=exp_args,
                            output_dir=args.output_dir,
                            max_phases=args.max_phases,
                            prompt_set_path=args.prompt_set,
                            prompt_dir=args.prompt_dir,
                            formatter=args.formatter,
                            context_as_tool=args.context_as_tool,
                            temperature=args.temperature,
                            use_likert=(not args.use_numeric),
                            likert_type=args.likert_type,
                            chronology=args.chronology,
                            parallel=args.parallel,
                        )
                    except Exception as e:
                        print(f"Error in default batch run for {csv_path}: {e}", file=sys.stderr)

if __name__ == "__main__":
    main()
