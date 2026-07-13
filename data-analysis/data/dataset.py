"""Build the unified annotation table from raw export directories.

The row contract (one row per game / source / run / observer / target / phase
/ trust_type) is what every analysis tool consumes; loaders in data/loaders
produce these rows. Files are matched to each other by `game_id` content, not
by filename, since filename conventions vary (e.g. `MISSING_VOTING_` prefixes).
"""

import hashlib
import json
from pathlib import Path

import pandas as pd

from core.logging import get_logger
from data.loaders.event_loader import is_events_file
from data.loaders.human_loader import human_rows, is_human_labels_file
from data.loaders.llm_loader import is_llm_run_file, llm_rows
from data.models.event import GameEventsFile
from data.models.experiment import LLMRun
from data.models.game import GameMeta
from data.models.human_observation import HumanGameLabels

logger = get_logger("data.dataset")

COLUMNS = [
    "game_id", "room_code", "game_mode", "winner", "exported_at",
    "source", "run_id",
    "observer", "observer_role", "observer_team", "observer_alive",
    "target", "target_role", "target_team", "target_alive",
    "round", "checkpoint", "phase_idx",
    "trust_type", "score_raw", "scale", "score_norm",
    "confidence_raw", "confidence_scale", "confidence_norm",
    "reasoning", "created_at",
    "model", "inner_voice_model", "experiment", "temperature",
    "trust_scale_mode", "formatter", "experiment_args", "max_phases",
    "context_as_tool",
]


def build_dataset(
    game_records_dir: Path | str,
    llm_results_dir: Path | str | None = None,
    use_ffill: bool = True,
) -> pd.DataFrame:
    """Load every recognized JSON export into one unified DataFrame.

    - `game_records_dir`: human labels + game events exports (webgame)
    - `llm_results_dir`: labeling engine outputs (searched recursively)
    """
    events_by_game: dict[str, GameEventsFile] = {}
    human_files: list[HumanGameLabels] = []
    llm_runs: list[LLMRun] = []

    for path in sorted(Path(game_records_dir).glob("*.json")):
        payload = _read_json(path)
        if payload is None:
            continue
        if is_events_file(payload):
            events_by_game[payload["game_id"]] = GameEventsFile(**payload)
        elif is_human_labels_file(payload):
            human_files.append(HumanGameLabels(**payload))
        else:
            logger.warning("Skipping unrecognized file: %s", path)

    if llm_results_dir is not None:
        for path in sorted(Path(llm_results_dir).rglob("*.json")):
            payload = _read_json(path)
            if payload is None:
                continue
            if is_llm_run_file(payload):
                run = LLMRun(**payload)
                run.run_id = path.stem
                llm_runs.append(run)
            else:
                logger.warning("Skipping unrecognized LLM result file: %s", path)

    rows = []
    for labels in human_files:
        events = events_by_game.get(labels.game_id)
        if events is None:
            logger.warning("No events export for game %s; phase alignment unavailable.", labels.game_id)
        rows.extend(human_rows(labels, events))

    meta_by_game: dict[str, GameMeta] = {g: e for g, e in events_by_game.items()}
    for run in llm_runs:
        events = events_by_game.get(run.game_id)
        if events is None:
            logger.warning("No events export for LLM run %s (game %s).", run.run_id, run.game_id)
        rows.extend(llm_rows(run, events, meta_by_game.get(run.game_id)))

    df = pd.DataFrame(rows, columns=COLUMNS)
    # The game never asks players to rate themselves, so observer==target rows
    # can only be labeling-engine glitches (the LLM including itself in the
    # target list); they would dilute means and heatmap diagonals downstream.
    self_labels = df["observer"] == df["target"]
    if self_labels.any():
        logger.warning(
            "Dropping %d self-label rows (observer == target), all from: %s",
            int(self_labels.sum()),
            sorted(df.loc[self_labels, "run_id"].dropna().unique()),
        )
        df = df[~self_labels].reset_index(drop=True)

    if use_ffill:
        df = apply_ffill(df)
    logger.info(
        "Dataset built (ffill=%s): %d rows (%d human files, %d LLM runs, %d games with events).",
        use_ffill, len(df), len(human_files), len(llm_runs), len(events_by_game),
    )
    return df


def apply_ffill(df: pd.DataFrame) -> pd.DataFrame:
    """Apply forward-fill and default fallback (4/7 trust, 2/3 confidence) to human rows."""
    human_df = df[df["source"] == "human"].copy()
    llm_df = df[df["source"] == "llm"].copy()
    
    if human_df.empty:
        return df

    groups = human_df.groupby(["game_id", "observer", "target", "trust_type"])
    filled_dfs = []
    
    for (game_id, observer, target, trust_type), group in groups:
        all_phases = sorted(df[df["game_id"] == game_id]["phase_idx"].dropna().unique())
        if not all_phases:
            filled_dfs.append(group)
            continue
            
        group = group.drop_duplicates(subset=["phase_idx"], keep="last")
        group = group.set_index("phase_idx")
        group = group.reindex(all_phases)
        
        group["game_id"] = game_id
        group["observer"] = observer
        group["target"] = target
        group["trust_type"] = trust_type
        group["source"] = "human"
        group["run_id"] = "human"
        group["scale"] = group["scale"].fillna("7pt")
        group["confidence_scale"] = group["confidence_scale"].fillna("3-level")
        
        valid_rows = group.dropna(subset=["room_code"])
        if not valid_rows.empty:
            first_row = valid_rows.iloc[0]
            for col in ["room_code", "game_mode", "winner", "exported_at", "observer_role", "observer_team", "target_role", "target_team"]:
                group[col] = group[col].fillna(first_row[col])
                
        group["score_raw"] = group["score_raw"].ffill()
        group["score_norm"] = group["score_norm"].ffill()
        group["confidence_raw"] = group["confidence_raw"].ffill()
        group["confidence_norm"] = group["confidence_norm"].ffill()
        
        group["observer_alive"] = group["observer_alive"].bfill().ffill()
        group["target_alive"] = group["target_alive"].bfill().ffill()
        
        group["score_raw"] = group["score_raw"].fillna(4.0)
        group["score_norm"] = group["score_norm"].fillna(0.5)
        group["confidence_raw"] = group["confidence_raw"].fillna(2.0)
        group["confidence_norm"] = group["confidence_norm"].fillna(0.5)
        
        group = group.reset_index()
        filled_dfs.append(group)
        
    filled_human_df = pd.concat(filled_dfs, ignore_index=True)
    return pd.concat([filled_human_df, llm_df], ignore_index=True)


def load_dataset(
    game_records_dir: Path | str,
    llm_results_dir: Path | str | None = None,
    cache_dir: Path | str | None = None,
    use_ffill: bool = True,
) -> pd.DataFrame:
    """`build_dataset` with a parquet cache keyed on input file stats.

    The cache is invalidated whenever any input file is added, removed, or
    modified (path/mtime/size fingerprint).
    """
    if cache_dir is None:
        return build_dataset(game_records_dir, llm_results_dir, use_ffill=use_ffill)

    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    fingerprint = _fingerprint(game_records_dir, llm_results_dir)
    
    # Isolate cache files for ffill vs raw
    parquet_name = "dataset.parquet" if use_ffill else "dataset_raw.parquet"
    parquet_path = cache_dir / parquet_name
    fingerprint_path = cache_dir / f"{parquet_name}.fingerprint"

    if parquet_path.exists() and fingerprint_path.exists():
        if fingerprint_path.read_text() == fingerprint:
            logger.info("Loading dataset from cache: %s", parquet_path)
            return pd.read_parquet(parquet_path)

    df = build_dataset(game_records_dir, llm_results_dir, use_ffill=use_ffill)
    df.to_parquet(parquet_path, index=False)
    fingerprint_path.write_text(fingerprint)
    return df


def _read_json(path: Path) -> dict | None:
    try:
        with open(path, encoding="utf-8") as f:
            payload = json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Could not read %s: %s", path, exc)
        return None
    return payload if isinstance(payload, dict) else None


def _fingerprint(game_records_dir: Path | str, llm_results_dir: Path | str | None) -> str:
    stats = []
    for directory, recursive in ((game_records_dir, False), (llm_results_dir, True)):
        if directory is None:
            continue
        directory = Path(directory)
        paths = directory.rglob("*.json") if recursive else directory.glob("*.json")
        for path in sorted(paths):
            stat = path.stat()
            stats.append(f"{path}:{stat.st_mtime_ns}:{stat.st_size}")
    return hashlib.sha256("\n".join(stats).encode()).hexdigest()
