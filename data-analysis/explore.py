"""Quick exploration of the unified trust dataset.

Run from the data-analysis directory:  uv run python explore.py
"""

from data.dataset import load_dataset
from data.filters import FilterSpec, apply_filters


def main() -> None:
    df = load_dataset(
        "../results/game-records",
        "../llm-labeling/results/llm-labeling",
        cache_dir="analysis/cache",
    )

    print(f"\nDataset: {len(df)} rows, {df['game_id'].nunique()} games")
    print(df.groupby("source").size().to_string())

    print("\n--- Alignment trust received, humans labeling ---")
    for team in ["WEREWOLVES", "VILLAGERS"]:
        spec = FilterSpec(sources=["human"], trust_types=["alignment"], target_teams=[team])
        rows = apply_filters(df, spec)
        print(f"  {team:<11} mean {rows['score_raw'].mean():.2f} / 7   (n={len(rows)})")

    print("\n--- Human vs LLM, alignment trust toward werewolves ---")
    for source in ["human", "llm"]:
        spec = FilterSpec(sources=[source], trust_types=["alignment"], target_teams=["WEREWOLVES"])
        rows = apply_filters(df, spec)
        if rows.empty:
            print(f"  {source:<6} no rows")
            continue
        print(f"  {source:<6} mean {rows['score_norm'].mean():.3f} (normalized)   (n={len(rows)})")

    print("\n--- Score distribution (raw 1-7), human vs LLM ---")
    seven_point = df[df["scale"] == "7pt"]
    counts = seven_point.groupby(["source", "score_raw"]).size().unstack(fill_value=0)
    print(counts.to_string())


if __name__ == "__main__":
    main()
