import argparse
import sys
from pathlib import Path

# src/ directory to Python's import path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from wolf_llm_labeling.game_records import GameRecord
from wolf_llm_labeling.models import LLMModelProviders

def main():
    parser = argparse.ArgumentParser(description="Print game context for a phase")
    parser.add_argument("--json", action="store_true", help="Print in JSON format instead of Markdown")
    parser.add_argument("--phase", type=int, default=0, help="Phase index to inspect (default: 0)")
    parser.add_argument("--player", type=str, default="Blue", help="Player name (default: Blue)")
    parser.add_argument("--game", type=str, default="game-44UT6Y-d59e923e.csv", help="Game record file name")
    parser.add_argument("--chronology", type=str, default="numeric", choices=["numeric", "timestamp"], help="Chronology formatting type")
    parser.add_argument("--experiment", type=str, default="a", help="Experiment module to load (default: a)")
    parser.add_argument("--experiment-args", type=str, default="", help="Config args for the experiment")
    parser.add_argument("--cutoff", type=int, help="Historical context cutoff")
    parser.add_argument("--variant", type=int, choices=[1, 2], help="Inner trust voice variant")
    parser.add_argument("--inner-voice-type", type=str, choices=["llm", "human", "random"], help="Inner voice type")
    
    args = parser.parse_args()

    # Compile separate parameters into experiment_args if provided
    if args.cutoff is not None or args.variant is not None or args.inner_voice_type is not None:
        compiled_parts = []
        cutoff_val = args.cutoff if args.cutoff is not None else 0
        compiled_parts.append(str(cutoff_val))
        
        if args.variant is not None or args.inner_voice_type is not None:
            variant_val = args.variant if args.variant is not None else 2
            compiled_parts.append(str(variant_val))
            
            if args.inner_voice_type is not None:
                compiled_parts.append(args.inner_voice_type)
        
        if not args.experiment_args:
            args.experiment_args = " ".join(compiled_parts)
    
    game_dir = Path(__file__).parent.parent / "results" / "game-records"
    game_path_csv = game_dir / args.game
    game_path_json = game_dir / args.game.replace(".csv", "-labels.json")
    
    if not game_path_csv.exists():
        print(f"Error: Could not find game record at {game_path_csv}")
        sys.exit(1)
        
    record = GameRecord()
    record.read_from_files([game_path_json, game_path_csv])
    
    models = LLMModelProviders(primary=None, inner_voice=None)
    import importlib
    exp_module = importlib.import_module(f"experiments.{args.experiment}")
    context_provider, _ = exp_module.experiment(args.player, args.experiment_args, models)
    
    from wolf_llm_labeling.models import active_player_name, chronology_type
    active_player_name.set(args.player)
    chronology_type.set(args.chronology)
    
    ctx_obj = context_provider.get_context(record, phase_idx=args.phase)
    
    if ctx_obj is not None:
        formatter = "json" if args.json else "markdown"
        print(ctx_obj.to_string(formatter_type=formatter))
    else:
        print("No context returned.")

if __name__ == "__main__":
    main()
