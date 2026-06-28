import sys
from pathlib import Path

# src/ directory to Python's import path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from wolf_llm_labeling.game_records import GameRecord
from experiments.d import experiment_d
from wolf_llm_labeling.inner_voice import RandomInnerVoice

def main():
    # Path
    game_path = Path(__file__).parent.parent / "results" / "game-records" / "game-CCUTH3-352fd9ba.csv"
    
    if not game_path.exists():
        print(f"Error: Could not find game record at {game_path.resolve()}")
        sys.exit(1)
        
    print(f"Loading game record: {game_path.name}")
    record = GameRecord()
    record.read_from_files(game_path)
    
    # Configure context builder parameters
    player_name = "Beige"
    cutoff = 3
    inner_voice = RandomInnerVoice()
    
    print(f"Generating context for player '{player_name}' at phase_idx=1 (cutoff={cutoff})...\n")
    context_provider, _ = experiment_d(player_name, cutoff, inner_voice, variant=2)
    
    # Retrieve context object
    ctx_obj = context_provider.get_context(record, phase_idx=1)
    
    if ctx_obj is not None:
        print(ctx_obj.to_string())
    else:
        print("No context returned.")

if __name__ == "__main__":
    main()
