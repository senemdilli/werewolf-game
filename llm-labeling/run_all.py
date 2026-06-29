import glob
import os
import sys
from pathlib import Path

repo_root = Path(__file__).resolve().parent
src_dir = repo_root / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

from wolf_llm_labeling.runner import run_labeling_experiment

def main():
    url = "https://gpu.snet.tu-berlin.de/echelon/ollama"
    models = ["gemma4:26b"] # Example llm model
    
    experiments = [ # Example values
        ("a", "3"),
        ("b", "3"),
        ("c", "3"),
        ("d", "3 2"),
        ("e", "3 2"),
        ("f", "3 2"),
    ]
    
    game_dir = repo_root / "results" / "game-records"
    csv_files = glob.glob(str(game_dir / "game-*.csv"))
    
    for csv_path in csv_files:
        json_path = csv_path.replace(".csv", "-labels.json")
        if not os.path.exists(json_path):
            continue
            
        for model in models:
            for exp, args in experiments:
                try:
                    run_labeling_experiment(
                        game_record_json=json_path,
                        game_record_csv=csv_path,
                        primary_model=model,
                        ollama_url=url,
                        experiment=exp,
                        experiment_args=args,
                        output_dir="./results/llm-labeling",
                    )
                except Exception as e:
                    print(f"Error executing {exp} with {model} on {csv_path}: {e}", file=sys.stderr)

if __name__ == "__main__":
    main()
