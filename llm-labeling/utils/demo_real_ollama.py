import os
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from wolf_llm_labeling.labeling import label_once
from wolf_llm_labeling.game_records import GameRecord
from wolf_llm_labeling.inner_voice import RandomInnerVoice
from experiments.d import experiment_d

# Initialize ChatOllama
try:
    from langchain_ollama import ChatOllama
except ImportError:
    try:
        from langchain_community.chat_models import ChatOllama
    except ImportError:
        print("Neither langchain_ollama nor langchain_community are installed.")
        print("Please run: pip install langchain-ollama")
        sys.exit(1)

token = os.getenv("OLLAMA_API_KEY")
if not token or token == "auth_token_":
    print("Warning: Please replace 'auth_token_' in .env with your actual Echelon token.")

llm = ChatOllama(
    model="gemma4:26b",
    temperature=0,
    base_url="https://gpu.snet.tu-berlin.de/echelon/ollama",
    client_kwargs={
        "headers": {
            "Authorization": f"Bearer {token}"
        }
    }
)

# Load game data
game_path = Path(__file__).parents[2] / "results" / "game-records" / "game-OX8OBY-3b3beea1.csv"
if not game_path.exists():
    print(f"Error: Game record CSV not found at {game_path}")
    sys.exit(1)

record = GameRecord()
record.read_from_files(game_path)

# Setup Experiment D, Variant 2 (Agentic Loop)
player_name = "Beatrix"
cutoff = 3
inner_voice = RandomInnerVoice() # random inner voice stub for demo

print(f"Setting up Experiment D (Variant 2) for player: {player_name} (cutoff: {cutoff})...")
context, iv_tool = experiment_d(player_name, cutoff, inner_voice, variant=2)

# Run the labeling loop
print("Executing label_once on real Ollama server (Agent Layer)...")
try:
    labels, call_info = label_once(
        llm_provider=llm,
        system_prompt="You are Beatrix, a werewolf. Evaluate the trust scores of other players.",
        context=context,
        inner_voice=iv_tool,
        game_data=record,
        phase_idx=0
    )

    print("\n=== Trust Labeling Results ===")
    for target, label in labels.items():
        print(f"\nPlayer: {target}")
        print(f"Reasoning: {label.reasoning}")
        ts = label.trust_scores
        if ts.alignment:
            print(f"  - Alignment Trust: {ts.alignment.trust}/7 (Confidence: {ts.alignment.confidence})")
        if ts.strategic:
            print(f"  - Strategic Trust: {ts.strategic.trust}/7 (Confidence: {ts.strategic.confidence})")
        if ts.consistency:
            print(f"  - Consistency Trust: {ts.consistency.trust}/7 (Confidence: {ts.consistency.confidence})")

    print("\n=== LLM Call Metadata ===")
    print(f"Provider: {call_info.provider_name}")
    print(f"Tool calls made: {len(call_info.tool_calls)}")
    print("=============================")

except Exception as e:
    print(f"\nError running LLM: {e}")
    print("If you get a connection error, please verify your internet connection or Echelon API token.")
