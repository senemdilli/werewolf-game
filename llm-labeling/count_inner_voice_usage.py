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

        files = [f for f in exp_dir.rglob("*.json") if not f.name.endswith("-trace.json")]

        if target_game:
            files = [f for f in files if target_game.lower() in f.name.lower() or target_game.lower() in str(f).lower()]

        if not files:
            print(f"No result files found for Experiment {exp.upper()}.\n")
            continue

        # Group by game & player
        runs_by_game = defaultdict(lambda: defaultdict(list))
        for fpath in sorted(files):
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                continue

            game_id = data.get("game_id", "unknown_game")
            room_code = data.get("room_code") or (game_id.split("-")[0] if "-" in game_id else game_id)
            player_name = data.get("player_name", "unknown_player")
            runs_by_game[room_code][player_name].append((fpath, data))

        print(f" EXPERIMENT {exp.upper()}")

        for room_code, player_map in sorted(runs_by_game.items()):
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
            phase_eval_counts = Counter()
            phase_call_counts = Counter()
            phase_active_players = defaultdict(set)

            for p_key, data in selected_player_runs.items():
                p_name = data.get("player_name", p_key)
                phases = data.get("phases", [])

                for p_data in phases:
                    p_idx = p_data.get("phase_idx")
                    phase_eval_counts[p_idx] += 1
                    total_phases += 1

                    iv_list = p_data.get("inner_voice", [])
                    num_calls = len(iv_list)

                    if num_calls > 0:
                        total_calls += num_calls
                        phase_call_counts[p_idx] += num_calls
                        phase_active_players[p_idx].add(p_name)

            avg_calls = round(total_calls / total_phases, 2) if total_phases > 0 else 0

            print(f"Game [{room_code}] ({len(selected_player_runs)} players evaluated, {total_phases} phase instances):")
            print(f"  -Total Inner Voice Calls: {total_calls} (Avg: {avg_calls} calls/phase)")
            print("  -Phase Breakdown:")
            for p_idx in sorted(phase_eval_counts.keys()):
                evals = phase_eval_counts[p_idx]
                calls = phase_call_counts[p_idx]
                p_cnt = len(phase_active_players[p_idx])
                avg_p = round(calls / evals, 2) if evals > 0 else 0
                print(f"   * Phase {p_idx}: {calls:<2} calls across {evals} player evaluations ({p_cnt} LLM players triggered tool, Avg: {avg_p:.2f} calls/phase)")
            print()

        print("-" * 70 + "\n")

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
