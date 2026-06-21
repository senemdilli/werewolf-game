"""Game record loading and accessors for exported Werewolf games."""

from __future__ import annotations

import csv
import json
import re
from collections import defaultdict
from dataclasses import dataclass
from json import JSONDecodeError
from pathlib import Path
from typing import Any

from wolf_llm_labeling.models import (
    ExileEvent,
    Forum,
    KillEvent,
    Label,
    MayorElected,
    Message,
    PhaseItem,
    PhaseType,
    PlayerName,
    PlayerStatus,
    Role,
    Score,
    SeerRevealed,
    SystemMessage,
    TrustScores,
    Vote,
    VoteReason,
    WitchKilled,
    WitchSaved,
)


class GameRecordError(Exception):
    """Base class for game record loading failures."""


class GameRecordParseError(GameRecordError, ValueError):
    """Raised when an export file cannot be parsed."""


class GameRecordValidationError(GameRecordError, ValueError):
    """Raised when parsed export data is inconsistent or invalid."""


_CSV_FIELDS = {
    "type",
    "game_id",
    "room_code",
    "game_mode",
    "winner",
    "round",
    "phase",
    "player_name",
    "player_role",
    "target_name",
    "content",
    "is_system",
    "timestamp",
}
_CHECKPOINT_TYPES = {
    "BEFORE_DISCUSSION": PhaseType.MORNING,
    "BEFORE_VOTING": PhaseType.DAY,
    "AFTER_VOTING": PhaseType.EVENING,
}
_CHECKPOINT_ORDER = tuple(_CHECKPOINT_TYPES)
_CONFIDENCE = {"LOW": 1, "MEDIUM": 2, "HIGH": 3}
_DAWN_DEATH_RE = re.compile(r"Dawn breaks\. (?P<victims>.+?) (?:was|were) found dead\.")
_PLAYER_WITH_ROLE_RE = re.compile(r"([^(),]+?)\s*\([^)]*\)")
_MAYOR_RE = re.compile(r"^(?P<player>.+?) has been elected Mayor\. Their vote counts double\.$")
_EXILE_RE = re.compile(r"^The village voted\. (?P<player>.+?) \([^)]*\) has been eliminated\.$")


@dataclass(frozen=True, slots=True)
class _CsvRow:
    path: Path
    number: int
    values: dict[str, str]


@dataclass(frozen=True, slots=True)
class _Phase:
    phase_type: PhaseType
    data: tuple[PhaseItem, ...]
    labels: dict[PlayerName, dict[PlayerName, tuple[Label, ...]]]
    statuses: dict[PlayerName, PlayerStatus]


class GameRecord:
    """Parsed game export with checkpoint-indexed phase accessors."""

    def __init__(self) -> None:
        self._players: dict[PlayerName, Role] = {}
        self._phases: tuple[_Phase, ...] = ()

    def read_from_files(self, paths: str | Path | list[str | Path]) -> None:
        """Load one CSV/labels export pair, replacing current state atomically."""

        csv_path, labels_path = _resolve_paths(paths)
        rows = _read_csv(csv_path)
        labels_doc = _read_json(labels_path)

        players: dict[PlayerName, Role] = {}
        _parse_csv_players(rows, players)
        phase_defs = _parse_labels(labels_path, labels_doc, players)
        _validate_game_ids(rows, labels_doc, csv_path, labels_path)
        phases = _build_phases(rows, phase_defs, players)

        self._players = dict(players)
        self._phases = tuple(phases)

    def get_players(self) -> dict[PlayerName, Role]:
        """Return player roles known from CSV player rows and labels."""

        return dict(self._players)

    def get_phase_type(self, phase_idx: int) -> PhaseType:
        return self._phase(phase_idx).phase_type

    def get_phase_data(self, phase_idx: int) -> list[PhaseItem]:
        return list(self._phase(phase_idx).data)

    def get_player_status(self, phase_idx: int, player_name: PlayerName) -> PlayerStatus:
        if player_name not in self._players:
            raise KeyError(player_name)
        return self._phase(phase_idx).statuses[player_name]

    def get_labels(self, phase_idx: int) -> dict[PlayerName, dict[PlayerName, list[Label]]]:
        return {
            observer: {target: list(labels) for target, labels in targets.items()}
            for observer, targets in self._phase(phase_idx).labels.items()
        }

    def _phase(self, phase_idx: int) -> _Phase:
        try:
            return self._phases[phase_idx]
        except IndexError:
            raise IndexError(f"Invalid phase index {phase_idx}; expected 0..{len(self._phases) - 1}.") from None


def _resolve_paths(paths: str | Path | list[str | Path]) -> tuple[Path, Path]:
    raw_paths = [Path(paths)] if isinstance(paths, str | Path) else [Path(path) for path in paths]
    if len(raw_paths) == 1:
        path = raw_paths[0]
        if path.suffix == ".csv":
            return path, path.with_name(f"{path.stem}-labels.json")
        if path.name.endswith("-labels.json"):
            return path.with_name(f"{path.name.removesuffix('-labels.json')}.csv"), path
        raise GameRecordValidationError(f"Unsupported game record path {path}; expected .csv or *-labels.json.")

    if len(raw_paths) != 2:
        raise GameRecordValidationError(f"Expected one CSV and one labels JSON path, got {len(raw_paths)} paths.")

    csv_paths = [path for path in raw_paths if path.suffix == ".csv"]
    label_paths = [path for path in raw_paths if path.name.endswith("-labels.json")]
    if len(csv_paths) != 1 or len(label_paths) != 1:
        raise GameRecordValidationError(f"Expected one CSV and one *-labels.json path, got {raw_paths}.")
    return csv_paths[0], label_paths[0]


def _read_csv(path: Path) -> list[_CsvRow]:
    if not path.exists():
        raise GameRecordParseError(f"Missing CSV file {path}.")
    try:
        with path.open(newline="", encoding="utf-8") as file:
            reader = csv.DictReader(file)
            if reader.fieldnames is None:
                raise GameRecordParseError(f"Missing CSV header in {path}.")
            missing = _CSV_FIELDS - set(reader.fieldnames)
            if missing:
                raise GameRecordValidationError(f"Missing CSV fields {sorted(missing)} in {path}.")

            rows = []
            for number, row in enumerate(reader, start=2):
                if None in row:
                    raise GameRecordParseError(f"Malformed CSV row {number} in {path}; unexpected extra columns.")
                rows.append(_CsvRow(path, number, {field: row.get(field, "") for field in _CSV_FIELDS}))
            return rows
    except csv.Error as exc:
        raise GameRecordParseError(f"Malformed CSV in {path}: {exc}.") from exc


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise GameRecordParseError(f"Missing labels JSON file {path}.")
    try:
        with path.open(encoding="utf-8") as file:
            data = json.load(file)
    except JSONDecodeError as exc:
        raise GameRecordParseError(f"Malformed JSON in {path} at line {exc.lineno}, column {exc.colno}: {exc.msg}.") from exc
    if not isinstance(data, dict):
        raise GameRecordValidationError(f"Invalid labels JSON in {path}; expected top-level object.")
    return data


def _validate_game_ids(rows: list[_CsvRow], labels_doc: dict[str, Any], csv_path: Path, labels_path: Path) -> None:
    csv_ids = {row.values["game_id"] for row in rows if row.values["game_id"]}
    if len(csv_ids) != 1:
        raise GameRecordValidationError(f"Invalid game_id values in {csv_path}; expected exactly one, got {sorted(csv_ids)}.")
    json_game_id = labels_doc.get("game_id")
    if not isinstance(json_game_id, str):
        raise GameRecordValidationError(f"Invalid game_id in {labels_path} at game_id; expected string.")
    csv_game_id = next(iter(csv_ids))
    if csv_game_id != json_game_id:
        raise GameRecordValidationError(
            f"Mismatched game_id between {csv_path} ({csv_game_id}) and {labels_path} ({json_game_id})."
        )


def _parse_csv_players(rows: list[_CsvRow], players: dict[PlayerName, Role]) -> None:
    for row in rows:
        name = row.values["player_name"]
        if not name or name == "System":
            continue
        role_value = row.values["player_role"]
        if not role_value:
            raise GameRecordValidationError(
                f"Invalid empty player_role in {row.path} row {row.number} field player_role for player {name}."
            )
        _add_player(players, name, _role(role_value, f"{row.path} row {row.number} field player_role"), str(row.path))


def _parse_labels(
    path: Path,
    labels_doc: dict[str, Any],
    players: dict[PlayerName, Role],
) -> list[tuple[int, str, dict[PlayerName, dict[PlayerName, tuple[Label, ...]]]]]:
    rounds = _expect_list(labels_doc, "rounds", path, "rounds")
    phases = []
    for round_index, round_doc in enumerate(rounds):
        round_path = f"rounds[{round_index}]"
        if not isinstance(round_doc, dict):
            raise GameRecordValidationError(f"Invalid round in {path} at {round_path}; expected object.")
        round_number = round_doc.get("round")
        if not isinstance(round_number, int):
            raise GameRecordValidationError(f"Invalid round number in {path} at {round_path}.round; expected integer.")
        checkpoints = _expect_list(round_doc, "checkpoints", path, f"{round_path}.checkpoints")
        for checkpoint_index, checkpoint_doc in enumerate(checkpoints):
            checkpoint_path = f"{round_path}.checkpoints[{checkpoint_index}]"
            if not isinstance(checkpoint_doc, dict):
                raise GameRecordValidationError(f"Invalid checkpoint in {path} at {checkpoint_path}; expected object.")
            checkpoint = checkpoint_doc.get("checkpoint")
            if checkpoint not in _CHECKPOINT_TYPES:
                raise GameRecordValidationError(
                    f"Invalid checkpoint {checkpoint!r} in {path} at {checkpoint_path}.checkpoint; "
                    f"expected one of {sorted(_CHECKPOINT_TYPES)}."
                )
            labels = _parse_checkpoint_labels(path, checkpoint_doc, players, f"{checkpoint_path}.labels")
            phases.append((round_number, checkpoint, labels))
    return phases


def _parse_checkpoint_labels(
    path: Path,
    checkpoint_doc: dict[str, Any],
    players: dict[PlayerName, Role],
    labels_path: str,
) -> dict[PlayerName, dict[PlayerName, tuple[Label, ...]]]:
    labels = _expect_list(checkpoint_doc, "labels", path, labels_path)
    by_observer: dict[PlayerName, dict[PlayerName, list[Label]]] = defaultdict(lambda: defaultdict(list))
    for label_index, label_doc in enumerate(labels):
        label_path = f"{labels_path}[{label_index}]"
        if not isinstance(label_doc, dict):
            raise GameRecordValidationError(f"Invalid label in {path} at {label_path}; expected object.")
        observer = _parse_player_ref(path, label_doc.get("observer"), players, f"{label_path}.observer")
        targets = _expect_list(label_doc, "targets", path, f"{label_path}.targets")
        for target_index, target_doc in enumerate(targets):
            target_path = f"{label_path}.targets[{target_index}]"
            if not isinstance(target_doc, dict):
                raise GameRecordValidationError(f"Invalid target in {path} at {target_path}; expected object.")
            target = _parse_player_ref(path, target_doc.get("player"), players, f"{target_path}.player")
            reasoning = target_doc.get("reasoning", "")
            if not isinstance(reasoning, str):
                raise GameRecordValidationError(f"Invalid reasoning in {path} at {target_path}.reasoning; expected string.")
            by_observer[observer][target].append(
                Label(
                    trust_scores=TrustScores(
                        alignment=_parse_score(path, target_doc, "alignment", f"{target_path}.alignment"),
                        strategic=_parse_score(path, target_doc, "information", f"{target_path}.information"),
                        consistency=_parse_score(path, target_doc, "consistency", f"{target_path}.consistency"),
                    ),
                    reasoning=reasoning,
                )
            )
    return {
        observer: {target: tuple(target_labels) for target, target_labels in targets.items()}
        for observer, targets in by_observer.items()
    }


def _parse_player_ref(path: Path, value: Any, players: dict[PlayerName, Role], json_path: str) -> PlayerName:
    if not isinstance(value, dict):
        raise GameRecordValidationError(f"Invalid player reference in {path} at {json_path}; expected object.")
    name = value.get("name")
    if not isinstance(name, str) or not name:
        raise GameRecordValidationError(f"Invalid player name in {path} at {json_path}.name; expected non-empty string.")
    role = _role(value.get("role"), f"{path} at {json_path}.role")
    _add_player(players, name, role, f"{path} at {json_path}")
    return name


def _parse_score(path: Path, target_doc: dict[str, Any], key: str, json_path: str) -> Score | None:
    if key not in target_doc:
        return None
    value = target_doc[key]
    if not isinstance(value, dict):
        raise GameRecordValidationError(f"Invalid score object in {path} at {json_path}; expected object.")
    trust = value.get("score")
    if not isinstance(trust, int) or not 1 <= trust <= 7:
        raise GameRecordValidationError(
            f"Invalid trust score {trust!r} in {path} at {json_path}.score; expected an integer from 1 to 7."
        )
    confidence = value.get("confidence")
    if confidence not in _CONFIDENCE:
        raise GameRecordValidationError(
            f"Invalid confidence {confidence!r} in {path} at {json_path}.confidence; "
            f"expected one of {sorted(_CONFIDENCE)}."
        )
    return Score(trust=trust, confidence=_CONFIDENCE[confidence])


def _expect_list(parent: dict[str, Any], key: str, path: Path, json_path: str) -> list[Any]:
    value = parent.get(key)
    if not isinstance(value, list):
        raise GameRecordValidationError(f"Invalid value in {path} at {json_path}; expected list.")
    return value


def _add_player(players: dict[PlayerName, Role], name: PlayerName, role: Role, source: str) -> None:
    existing = players.get(name)
    if existing is not None and existing != role:
        raise GameRecordValidationError(f"Conflicting role for player {name!r} in {source}: {existing.value} vs {role.value}.")
    players[name] = role


def _role(value: Any, source: str) -> Role:
    if not isinstance(value, str):
        raise GameRecordValidationError(f"Invalid role {value!r} in {source}; expected role string.")
    try:
        return Role(value.strip().title())
    except ValueError as exc:
        expected = [role.name for role in Role]
        raise GameRecordValidationError(f"Invalid role {value!r} in {source}; expected one of {expected}.") from exc


def _build_phases(
    rows: list[_CsvRow],
    phase_defs: list[tuple[int, str, dict[PlayerName, dict[PlayerName, tuple[Label, ...]]]]],
    players: dict[PlayerName, Role],
) -> list[_Phase]:
    row_items = _collect_row_items(rows)
    phase_items: dict[tuple[int, str], list[tuple[tuple[int, int], PhaseItem]]] = defaultdict(list)
    checkpoints_by_round: dict[int, list[str]] = defaultdict(list)
    for round_number, checkpoint, _labels in phase_defs:
        checkpoints_by_round[round_number].append(checkpoint)

    for (round_number, source_checkpoint), items in row_items.items():
        target_checkpoint = _target_checkpoint(source_checkpoint, checkpoints_by_round.get(round_number, []))
        if target_checkpoint is not None:
            phase_items[(round_number, target_checkpoint)].extend(items)

    phases = []
    statuses = {player: PlayerStatus.ALIVE for player in players}
    mayor: PlayerName | None = None
    for round_number, checkpoint, labels in phase_defs:
        data = tuple(item for _sort_key, item in sorted(phase_items.get((round_number, checkpoint), []), key=lambda item: item[0]))
        statuses, mayor, status_snapshot = _apply_statuses(statuses, mayor, data)
        phases.append(_Phase(_CHECKPOINT_TYPES[checkpoint], data, labels, status_snapshot))
    return phases


def _collect_row_items(rows: list[_CsvRow]) -> dict[tuple[int, str], list[tuple[tuple[int, int], PhaseItem]]]:
    first_day_player: dict[int, int] = {}
    voting_begins: dict[int, int] = {}
    for row in rows:
        values = row.values
        if values["type"] == "chat" and values["phase"] == "DAY":
            round_number = _round_number(row)
            if values["is_system"] == "false":
                first_day_player.setdefault(round_number, row.number)
            if values["is_system"] == "true" and values["content"] == "Voting begins.":
                voting_begins.setdefault(round_number, row.number)

    items: dict[tuple[int, str], list[tuple[tuple[int, int], PhaseItem]]] = defaultdict(list)
    for row in rows:
        row_type = row.values["type"]
        if row_type == "note":
            # ponytail: private notes need a future role-memory model, not GameRecord phase items.
            continue
        round_number = _round_number(row)
        if row_type == "chat":
            checkpoint, sort_group = _chat_checkpoint(row, first_day_player, voting_begins)
            for item in _parse_chat_row(row):
                items[(round_number, checkpoint)].append(((sort_group, row.number), item))
            continue
        if row_type == "night_action":
            items[(round_number, "BEFORE_DISCUSSION")].append(((1, row.number), _parse_night_action(row)))
            continue
        raise GameRecordParseError(
            f"Unknown row type {row_type!r} in {row.path} row {row.number} field type; "
            "expected chat, night_action, or note."
        )
    return items


def _chat_checkpoint(
    row: _CsvRow,
    first_day_player: dict[int, int],
    voting_begins: dict[int, int],
) -> tuple[str, int]:
    phase = row.values["phase"]
    if phase == "NIGHT":
        return "BEFORE_DISCUSSION", 0
    if phase != "DAY":
        raise GameRecordValidationError(
            f"Invalid phase {phase!r} in {row.path} row {row.number} field phase; expected DAY or NIGHT."
        )
    round_number = _round_number(row)
    voting_row = voting_begins.get(round_number)
    if row.values["content"] == "Voting begins." or (voting_row is not None and row.number >= voting_row):
        return "AFTER_VOTING", 0
    first_player_row = first_day_player.get(round_number)
    if row.values["is_system"] == "true" and (first_player_row is None or row.number < first_player_row):
        return "BEFORE_DISCUSSION", 2
    return "BEFORE_VOTING", 0


def _parse_chat_row(row: _CsvRow) -> list[PhaseItem]:
    is_system = row.values["is_system"]
    if is_system not in {"true", "false"}:
        raise GameRecordValidationError(
            f"Invalid is_system {is_system!r} in {row.path} row {row.number} field is_system; expected true or false."
        )
    if is_system == "true":
        return _parse_system_text(row)

    player_name = row.values["player_name"]
    if not player_name or player_name == "System":
        raise GameRecordValidationError(
            f"Invalid player_name {player_name!r} in {row.path} row {row.number} field player_name; expected real player."
        )
    phase = row.values["phase"]
    role = _role(row.values["player_role"], f"{row.path} row {row.number} field player_role")
    if phase == "DAY":
        forum = Forum.VILLAGE_CHAT
    elif phase == "NIGHT" and role == Role.WEREWOLF:
        forum = Forum.WEREWOLF_CHAT
    elif phase == "NIGHT":
        raise GameRecordParseError(
            f"Cannot classify NIGHT chat for non-werewolf role {role.value} in {row.path} row {row.number}; "
            "expected werewolf chat or a structured role action."
        )
    else:
        raise GameRecordValidationError(
            f"Invalid phase {phase!r} in {row.path} row {row.number} field phase; expected DAY or NIGHT."
        )
    return [Message(forum=forum, player_name=player_name, message=row.values["content"])]


def _parse_system_text(row: _CsvRow) -> list[PhaseItem]:
    content = row.values["content"]
    death_match = _DAWN_DEATH_RE.match(content)
    if death_match:
        victims = [
            re.sub(r"^(?:and|or)\s+", "", match.group(1).strip())
            for match in _PLAYER_WITH_ROLE_RE.finditer(death_match.group("victims"))
        ]
        if victims:
            return [KillEvent(victim) for victim in victims]
    mayor_match = _MAYOR_RE.match(content)
    if mayor_match:
        return [MayorElected(mayor_match.group("player"))]
    exile_match = _EXILE_RE.match(content)
    if exile_match:
        return [ExileEvent(exile_match.group("player"))]
    if content == "The village voted to skip. No one was eliminated.":
        return [ExileEvent(None)]
    return [SystemMessage(message=content)]


def _parse_night_action(row: _CsvRow) -> PhaseItem:
    actor = row.values["player_name"]
    target = row.values["target_name"]
    action = row.values["content"]
    if not actor:
        raise GameRecordValidationError(f"Invalid empty player_name in {row.path} row {row.number} field player_name.")
    if not target:
        raise GameRecordValidationError(f"Invalid empty target_name in {row.path} row {row.number} field target_name.")
    if action == "KILL":
        return Vote(reason=VoteReason.KILL, player_name=actor, voted_for=target)
    if action == "INVESTIGATE":
        return SeerRevealed(target)
    if action == "HEAL":
        return WitchSaved(target)
    if action == "WITCH_KILL":
        return WitchKilled(target)
    raise GameRecordParseError(
        f"Unknown night_action {action!r} in {row.path} row {row.number} field content; "
        "expected KILL, INVESTIGATE, HEAL, or WITCH_KILL."
    )


def _round_number(row: _CsvRow) -> int:
    value = row.values["round"]
    try:
        round_number = int(value)
    except ValueError as exc:
        raise GameRecordValidationError(
            f"Invalid round {value!r} in {row.path} row {row.number} field round; expected integer."
        ) from exc
    if round_number < 1:
        raise GameRecordValidationError(
            f"Invalid round {value!r} in {row.path} row {row.number} field round; expected positive integer."
        )
    return round_number


def _target_checkpoint(source_checkpoint: str, existing_checkpoints: list[str]) -> str | None:
    if not existing_checkpoints:
        return None
    if source_checkpoint in existing_checkpoints:
        return source_checkpoint
    source_index = _CHECKPOINT_ORDER.index(source_checkpoint)
    for checkpoint in _CHECKPOINT_ORDER[source_index + 1 :]:
        if checkpoint in existing_checkpoints:
            return checkpoint
    for checkpoint in reversed(_CHECKPOINT_ORDER[:source_index]):
        if checkpoint in existing_checkpoints:
            return checkpoint
    return None


def _apply_statuses(
    statuses: dict[PlayerName, PlayerStatus],
    mayor: PlayerName | None,
    data: tuple[PhaseItem, ...],
) -> tuple[dict[PlayerName, PlayerStatus], PlayerName | None, dict[PlayerName, PlayerStatus]]:
    next_statuses = dict(statuses)
    next_mayor = mayor
    for item in data:
        if isinstance(item, MayorElected) and item.affected_player in next_statuses:
            if next_statuses[item.affected_player] == PlayerStatus.ALIVE:
                next_mayor = item.affected_player
        elif isinstance(item, KillEvent | WitchKilled) and item.affected_player in next_statuses:
            next_statuses[item.affected_player] = PlayerStatus.DEAD
            if next_mayor == item.affected_player:
                next_mayor = None
        elif isinstance(item, ExileEvent) and item.affected_player in next_statuses:
            next_statuses[item.affected_player] = PlayerStatus.EXILED
            if next_mayor == item.affected_player:
                next_mayor = None

    snapshot = dict(next_statuses)
    if next_mayor is not None and snapshot.get(next_mayor) == PlayerStatus.ALIVE:
        snapshot[next_mayor] = PlayerStatus.MAYOR
    return next_statuses, next_mayor, snapshot
