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
    logger.info(
        "Dataset built: %d rows (%d human files, %d LLM runs, %d games with events).",
        len(df), len(human_files), len(llm_runs), len(events_by_game),
    )
    return df


def load_dataset(
    game_records_dir: Path | str,
    llm_results_dir: Path | str | None = None,
    cache_dir: Path | str | None = None,
) -> pd.DataFrame:
    """`build_dataset` with a parquet cache keyed on input file stats.

    The cache is invalidated whenever any input file is added, removed, or
    modified (path/mtime/size fingerprint).
    """
    if cache_dir is None:
        return build_dataset(game_records_dir, llm_results_dir)

    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    fingerprint = _fingerprint(game_records_dir, llm_results_dir)
    parquet_path = cache_dir / "dataset.parquet"
    fingerprint_path = cache_dir / "dataset.fingerprint"

    if parquet_path.exists() and fingerprint_path.exists():
        if fingerprint_path.read_text() == fingerprint:
            logger.info("Loading dataset from cache: %s", parquet_path)
            return pd.read_parquet(parquet_path)

    df = build_dataset(game_records_dir, llm_results_dir)
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
