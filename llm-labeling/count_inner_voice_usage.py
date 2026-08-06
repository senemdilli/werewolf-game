"""
Count Inner Voice tool calls (ask_inner_trust_voice) per phase across LLM labeling runs
Usage with Example game:
    cd llm-labeling
    python count_inner_voice_usage.py --game UBY0T7
"""

import argparse
import glob
import json
import os
from collections import Counter, defaultdict
from pathlib import Path

def analyze_inner_voice_usage(results_dir: str, target_game: str | None = None, dedup: bool = True):
    base_path = Path(results_dir).resolve()
    if not base_path.exists():
        print(f"Error: Results directory '{base_path}' does not exist")
        return

    experiments = ["d", "e", "f"]
    print("########################" "\n")
    print(f"Inner Voice Tool Usage Report ({'Latest run per player' if dedup else 'All JSON Files'})")
    if target_game:
        print(f"Filter Game: {target_game}")
    print("########################" "\n")

    for exp in experiments:
        exp_dir = base_path / exp
        if not exp_dir.exists():
            print(f"Skipping Experiment {exp.upper()}: Directory not found ({exp_dir})")
            continue

        files = [f for f in exp_dir.rglob("*.json") if not f.name.endswith("-trace.json") and not f.name.endswith("-trace.md")]

        if target_game:
            files = [f for f in files if target_game.lower() in f.name.lower() or target_game.lower() in str(f).lower()]

        if not files:
            print(f"No result files found for Experiment {exp.upper()}.\n")
            continue

        # Group by game & model & player
        runs_by_game = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
        for fpath in sorted(files):
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                continue

            game_id = data.get("game_id", "unknown_game")
            room_code = data.get("room_code") or (game_id.split("-")[0] if "-" in game_id else game_id)
            player_name = data.get("player_name", "unknown_player")
            model_name = fpath.parent.name if fpath.parent != exp_dir else "default_model"
            runs_by_game[room_code][model_name][player_name].append((fpath, data))

        print(f" EXPERIMENT {exp.upper()}")

        for room_code, model_map in sorted(runs_by_game.items()):
            all_game_phases = set()
            model_stats = {}

            for model_name, player_map in sorted(model_map.items()):
                selected_player_runs = {}

                if dedup:
                    # Keep latest file per player
                    for p_name, file_list in player_map.items():
                        latest_tuple = sorted(file_list, key=lambda x: x[0].name)[-1]
                        selected_player_runs[p_name] = latest_tuple[1]
                else:
                    for p_name, file_list in player_map.items():
                        for idx, (fpath, data) in enumerate(file_list):
                            selected_player_runs[f"{p_name}_{idx}"] = data

                total_phases = 0
                total_calls = 0
                phase_call_counts = Counter()

                for p_key, data in selected_player_runs.items():
                    phases = data.get("phases", [])
                    for p_data in phases:
                        p_idx = p_data.get("phase_idx")
                        if p_idx is None:
                            continue
                        all_game_phases.add(p_idx)
                        total_phases += 1

                        num_calls = len(p_data.get("inner_voice", []))
                        if num_calls > 0:
                            total_calls += num_calls
                            phase_call_counts[p_idx] += num_calls

                avg_eval = round(total_calls / total_phases, 2) if total_phases > 0 else 0
                model_stats[model_name] = {
                    "total_calls": total_calls,
                    "avg_eval": avg_eval,
                    "phase_calls": phase_call_counts,
                    "players_count": len(selected_player_runs),
                    "total_phases": total_phases
                }

            sorted_phases = sorted(all_game_phases)
            first_m = list(model_stats.keys())[0]
            n_players = model_stats[first_m]["players_count"]
            n_evals = model_stats[first_m]["total_phases"]

            print(f"Game [{room_code}] ({n_players} players, {n_evals} phase evaluations):")
            p_hdr = "  ".join([f"P{p:<2}" for p in sorted_phases])
            header_str = f"Model                Total    Calls/Eval   {p_hdr}"
            print(header_str)
            print("_" * len(header_str))

            for m_name, stats in model_stats.items():
                pc = stats["phase_calls"]
                p_str = "  ".join([f"{pc.get(p, 0):<3}" for p in sorted_phases])
                tc = stats["total_calls"]
                ae = stats["avg_eval"]
                print(f"{m_name:<20} {tc:>5}     {ae:>6.2f}/eval   {p_str}")
            print()

        print("_" * 70 + "\n")

def main():
    parser = argparse.ArgumentParser(description="Count Inner Voice tool calls in LLM labeling runs")
    parser.add_argument("--results-dir", type=str, default="../results/llm-labeling", help="Directory containing experiment results")
    parser.add_argument("--game", type=str, help="Filter by specific game room code or ID (e.g. UBY0T7 or 5NOHGS)")
    parser.add_argument("--all-runs", action="store_true", help="Include duplicate runs instead of keeping only the latest run per player")
    
    args = parser.parse_args()

    # Fallback
    res_path = Path(args.results_dir)
    if not res_path.exists() and Path("./results/llm-labeling").exists():
        res_path = Path("./results/llm-labeling")

    analyze_inner_voice_usage(
        results_dir=str(res_path),
        target_game=args.game,
        dedup=not args.all_runs
    )

if __name__ == "__main__":
    main()
