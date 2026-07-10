"""Compare LLM labeling runs against human labels on the same games.

Run from the data-analysis directory:

    uv run python compare_llm.py                # all games with LLM runs
    uv run python compare_llm.py --game 5NOHGS  # one game only

Shows which LLM runs are loaded, then compares human and LLM trust scores on
matched cells — same game, same observer, same target, same phase, same trust
dimension — which is the apples-to-apples version of the human-vs-LLM delta.
"""

import argparse

import pandas as pd

from data.dataset import load_dataset
from data.filters import FilterSpec, apply_filters

MATCH_KEYS = ["game_id", "room_code", "observer", "target", "phase_idx", "trust_type"]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game", help="restrict to one room code, e.g. 5NOHGS")
    parser.add_argument("--game-records", default="../results/game-records")
    parser.add_argument("--llm-results", default="../llm-labeling/results/llm-labeling")
    args = parser.parse_args()

    df = load_dataset(args.game_records, args.llm_results, cache_dir="analysis/cache")
    if args.game:
        df = apply_filters(df, FilterSpec(room_codes=[args.game]))

    llm = apply_filters(df, FilterSpec(sources=["llm"]))
    if llm.empty:
        print("No LLM runs found — check the results directory path / --game filter.")
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

    print("\n--- Per game ---")
    per_game = matched.groupby("room_code").apply(
        lambda g: pd.Series({
            "cells": len(g),
            "mean delta": g["delta"].mean(),
            "mean abs delta": g["delta"].abs().mean(),
            "spearman": _spearman(g),
        }),
        include_groups=False,
    )
    print(per_game.round(3).to_string())

    print("\n--- Per trust dimension (all matched games) ---")
    per_type = matched.groupby("trust_type")["delta"].agg(["mean", lambda s: s.abs().mean(), "size"])
    per_type.columns = ["mean delta (llm - human)", "mean abs delta", "n"]
    print(per_type.round(3).to_string())

    print("\n--- Per phase (all matched games) ---")
    per_phase = matched.groupby("phase_idx")["delta"].agg(["mean", "size"])
    per_phase.columns = ["mean delta", "n"]
    print(per_phase.round(3).to_string())

    print(f"\nSpearman correlation human vs LLM on all matched cells: {_spearman(matched):.3f}")

    _team_trust_comparison(df, llm)


def _spearman(cells: pd.DataFrame) -> float:
    if len(cells) < 3:
        return float("nan")
    return cells["human"].corr(cells["llm"], method="spearman")


def _team_trust_comparison(df: pd.DataFrame, llm: pd.DataFrame) -> None:
    """Alignment trust received by team, human vs LLM, per game with LLM runs.

    Uses all annotations (not just matched cells): the question is whether each
    source's overall suspicion points at the werewolves, which doesn't require
    identical observers.
    """
    print("\n--- Alignment trust received by team, per game (raw 1-7, self excluded) ---")
    rows = apply_filters(df, FilterSpec(trust_types=["alignment"], exclude_self=True))
    rows = rows[rows["scale"] == "7pt"]
    rows = rows[rows["room_code"].isin(llm["room_code"].unique())]
    by_team = (
        rows.groupby(["room_code", "source", "target_team"])["score_raw"]
        .mean()
        .unstack("target_team")
        .round(2)
    )
    by_team["gap (V - W)"] = (by_team.get("VILLAGERS") - by_team.get("WEREWOLVES")).round(2)
    print(by_team.to_string())
    print("(positive gap = suspicion points at the werewolves; negative = the wolves are winning the trust game)")


if __name__ == "__main__":
    main()
