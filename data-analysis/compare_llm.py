"""Compare LLM labeling runs against human labels on the same games.

Run from the data-analysis directory:  uv run python compare_llm.py

Shows which LLM runs are loaded, then compares human and LLM trust scores on
matched cells — same game, same observer, same target, same phase, same trust
dimension — which is the apples-to-apples version of the human-vs-LLM delta.
"""

import pandas as pd

from data.dataset import load_dataset
from data.filters import FilterSpec, apply_filters

MATCH_KEYS = ["game_id", "observer", "target", "phase_idx", "trust_type"]


def main() -> None:
    df = load_dataset(
        "../results/game-records",
        "../llm-labeling/results/llm-labeling",
        cache_dir="analysis/cache",
    )

    llm = apply_filters(df, FilterSpec(sources=["llm"]))
    if llm.empty:
        print("No LLM runs found — check the results directory path.")
        return

    print("\n--- LLM runs loaded ---")
    runs = llm.groupby("run_id").agg(
        game=("room_code", "first"),
        observer=("observer", "first"),
        model=("model", "first"),
        experiment=("experiment", "first"),
        scale=("scale", "first"),
        phases=("phase_idx", "nunique"),
        rows=("score_raw", "size"),
    )
    print(runs.to_string())

    human = apply_filters(df, FilterSpec(sources=["human"]))

    # Average LLM runs per cell so repeated runs don't overweight a cell,
    # then join with the human score for the identical cell.
    llm_cells = llm.groupby(MATCH_KEYS)["score_norm"].mean().rename("llm")
    human_cells = human.groupby(MATCH_KEYS)["score_norm"].mean().rename("human")
    matched = pd.concat([human_cells, llm_cells], axis=1, join="inner").reset_index()

    print(f"\n--- Matched cells (same game/observer/target/phase/dimension): {len(matched)} ---")
    if matched.empty:
        print("No overlap: the loaded LLM runs label players/phases no human annotated.")
        print("(Human labels exist only where that player submitted the in-game form.)")
        return

    matched["delta"] = matched["llm"] - matched["human"]
    per_type = matched.groupby("trust_type")["delta"].agg(["mean", lambda s: s.abs().mean(), "size"])
    per_type.columns = ["mean delta (llm - human)", "mean abs delta", "n"]
    print(per_type.to_string())

    print("\n--- Per-phase delta (all matched cells) ---")
    per_phase = matched.groupby("phase_idx")["delta"].agg(["mean", "size"])
    per_phase.columns = ["mean delta", "n"]
    print(per_phase.to_string())

    corr = matched["human"].corr(matched["llm"], method="spearman")
    print(f"\nSpearman correlation human vs LLM on matched cells: {corr:.3f}")


if __name__ == "__main__":
    main()
