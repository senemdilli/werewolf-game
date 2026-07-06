"""Quick exploration of the unified trust dataset — all games, both sources.

Run from the data-analysis directory:

    uv run python explore.py                # everything
    uv run python explore.py --game 5NOHGS  # one game only
"""

import argparse

import pandas as pd

from data.dataset import load_dataset
from data.filters import FilterSpec, apply_filters


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game", help="restrict to one room code, e.g. 5NOHGS")
    parser.add_argument("--game-records", default="../results/game-records")
    parser.add_argument("--llm-results", default="../llm-labeling/results/llm-labeling")
    args = parser.parse_args()

    df = load_dataset(args.game_records, args.llm_results, cache_dir="analysis/cache")
    if args.game:
        df = apply_filters(df, FilterSpec(room_codes=[args.game]))
        if df.empty:
            print(f"No rows for game {args.game!r}.")
            return

    print(f"\nDataset: {len(df)} rows, {df['game_id'].nunique()} games")
    print(df.groupby("source").size().to_string())

    print("\n--- Per game: annotation coverage ---")
    coverage = pd.DataFrame({
        "winner": df.groupby("room_code")["winner"].first(),
        "human rows": df[df["source"] == "human"].groupby("room_code").size(),
        "llm rows": df[df["source"] == "llm"].groupby("room_code").size(),
        "llm runs": df[df["source"] == "llm"].groupby("room_code")["run_id"].nunique(),
    }).fillna(0).astype({"human rows": int, "llm rows": int, "llm runs": int})
    print(coverage.to_string())

    print("\n--- Alignment trust received by team (does trust track hidden roles?) ---")
    print("mean raw score 1-7, self-ratings excluded; games without both teams rated show NaN")
    spec = FilterSpec(trust_types=["alignment"], exclude_self=True)
    rows = apply_filters(df, spec)
    rows = rows[rows["scale"] == "7pt"]  # keep scales comparable
    by_team = (
        rows.groupby(["room_code", "source", "target_team"])["score_raw"]
        .mean()
        .unstack("target_team")
        .round(2)
    )
    by_team["gap (V - W)"] = (by_team.get("VILLAGERS") - by_team.get("WEREWOLVES")).round(2)
    print(by_team.to_string())
    print("(positive gap = werewolves trusted less than villagers, i.e. suspicion points the right way)")

    print("\n--- Score distribution (raw 1-7): who rates more extremely? ---")
    seven_point = df[df["scale"] == "7pt"]
    counts = seven_point.groupby(["source", "score_raw"]).size().unstack(fill_value=0)
    print(counts.to_string())


if __name__ == "__main__":
    main()
