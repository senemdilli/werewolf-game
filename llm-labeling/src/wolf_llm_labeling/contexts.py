"""Context builder interfaces and stubs for LLM-visible game state."""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING, Protocol

from wolf_llm_labeling.game_records import GameRecord
from wolf_llm_labeling.models import (
    ExileEvent,
    Forum,
    KillEvent,
    Label,
    MayorElected,
    Message,
    PhaseItem,
    PlayerName,
    Role,
    Score,
    SeerRevealed,
    SystemMessage,
    TrustScores,
    Vote,
    WitchKilled,
    WitchSaved,
    FormatterType,
    VoteReason,
    PhaseType,
)
from wolf_llm_labeling.prompts import PromptSet

if TYPE_CHECKING:
    from wolf_llm_labeling.inner_voice import InnerVoice


class Ctx:
    __slots__ = ("header", "content", "subsections")

    header: str | None
    content: str | None
    subsections: tuple["Ctx", ...]

    def __init__(
        self,
        header: str | None = None,
        content: str | None = None,
        subsections: Iterable["Ctx"] | None = None,
    ) -> None:
        subsection_tuple = () if subsections is None else tuple(subsections)
        for index, subsection in enumerate(subsection_tuple):
            if not isinstance(subsection, Ctx):
                raise TypeError(
                    f"Ctx subsections must be Ctx instances, got {type(subsection).__name__} at index {index}."
                )

        self.header = header
        self.content = content
        self.subsections = subsection_tuple

    def is_empty(self) -> bool:
        return (
            _visible_text(self.header) is None
            and _visible_text(self.content) is None
            and all(subsection.is_empty() for subsection in self.subsections)
        )

    def to_string(self, formatter_type: FormatterType = "markdown", level: int = 1) -> str:
        if formatter_type == "json":
            import json
            return json.dumps(self.to_dict(), indent=2)
        else:
            return self._render(level)

    def to_dict(self) -> dict[str, Any]:
        res: dict[str, Any] = {}
        header = _visible_text(self.header)
        content = _visible_text(self.content)
        if header is not None:
            res["header"] = header
        if content is not None:
            res["content"] = content
        if self.subsections:
            res["subsections"] = [sub.to_dict() for sub in self.subsections]
        return res

    def __str__(self) -> str:
        return self.to_string()

    def _render(self, heading_level: int) -> str:
        header = _visible_text(self.header)
        content = _visible_text(self.content)
        child_heading_level = heading_level + 1 if header is not None else heading_level
        blocks = []

        if header is not None:
            blocks.append(f"{'#' * min(heading_level, 6)} {header}")
        if content is not None:
            blocks.append(content)
        for subsection in self.subsections:
            rendered = subsection._render(child_heading_level)
            if rendered:
                blocks.append(rendered)

        return "\n\n".join(blocks)


def _visible_text(value: str | None) -> str | None:
    if value is None:
        return None
    text = value.strip()
    return text or None


def _bullet_lines(lines: list[str]) -> list[str]:
    """Prefix each top-level line with "- " when dash list style is active.

    Already-indented sub-lines (e.g. "  - Purple (Villager): killed") are left
    untouched so nested bullets keep their existing indentation.
    """
    from wolf_llm_labeling.models import list_style

    if list_style.get() != "dash":
        return lines
    return [line if line.startswith(" ") else f"- {line}" for line in lines]


class ContextProvider(Protocol):
    def get_context(self, game_record: GameRecord, prompt_set: PromptSet, phase_idx: int) -> "Ctx | None": ...

    def get_topness(self) -> float: ...


class JoinedContext:
    __slots__ = ("header", "content", "topness", "sub_contexts")

    def __init__(
        self,
        header: str | None,
        content: str | None,
        topness: float,
        *sub_contexts: ContextProvider,
    ) -> None:
        self.header = header
        self.content = content
        self.topness = topness
        self.sub_contexts = tuple(sub_contexts)

    def get_context(
        self,
        game_record: GameRecord,
        prompt_set_or_phase_idx: Any = None,
        phase_idx: int | None = None,
    ) -> Ctx | None:
        if phase_idx is None:
            target_phase_idx = prompt_set_or_phase_idx
            prompt_set = PromptSet()
        else:
            target_phase_idx = phase_idx
            prompt_set = prompt_set_or_phase_idx if isinstance(prompt_set_or_phase_idx, PromptSet) else PromptSet()

        child_contexts = []
        for provider in self.sub_contexts:
            import inspect
            try:
                sig = inspect.signature(provider.get_context)
                pos_params = [
                    p for p in sig.parameters.values()
                    if p.kind in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
                ]
                if len(pos_params) >= 3:
                    context = provider.get_context(game_record, prompt_set, target_phase_idx)
                else:
                    context = provider.get_context(game_record, target_phase_idx)
            except Exception:
                try:
                    context = provider.get_context(game_record, prompt_set, target_phase_idx)
                except TypeError:
                    context = provider.get_context(game_record, target_phase_idx)

            if context is None or context.is_empty():
                continue
            child_contexts.append((provider.get_topness(), context))

        child_contexts.sort(key=lambda item: item[0], reverse=True)
        subsections = [context for _, context in child_contexts]

        if _visible_text(self.content) is None and not subsections:
            return None

        return Ctx(
            header=self.header,
            content=self.content,
            subsections=subsections,
        )

    def get_topness(self) -> float:
        return self.topness


class StaticContext:
    player_name: PlayerName

    def __init__(self, player_name: PlayerName) -> None:
        self.player_name = player_name

    def get_context(
        self,
        game_record: GameRecord,
        prompt_set_or_phase_idx: Any = None,
        phase_idx: int | None = None,
    ) -> Ctx | None:
        if phase_idx is None:
            target_phase_idx = prompt_set_or_phase_idx
            prompt_set = PromptSet()
        else:
            target_phase_idx = phase_idx
            prompt_set = prompt_set_or_phase_idx if isinstance(prompt_set_or_phase_idx, PromptSet) else PromptSet()

        players = game_record.get_players()
        
        if self.player_name not in players:
            return None
        
        role = players[self.player_name]

        static_lines = [
            f"Your name is: {self.player_name}",
            f"Your role is: {role.value}",
        ]
        return Ctx(
            header="Static Data",
            content="\n".join(_bullet_lines(static_lines)),
        )

    def get_topness(self) -> float:
        return 100.0


class GameNowContext:
    
    def __init__(self, player_name: PlayerName) -> None:
        self.player_name = player_name

    def get_context(
        self,
        game_record: GameRecord,
        prompt_set_or_phase_idx: Any = None,
        phase_idx: int | None = None,
    ) -> Ctx | None:
        if phase_idx is None:
            target_phase_idx = prompt_set_or_phase_idx
            prompt_set = PromptSet()
        else:
            target_phase_idx = phase_idx
            prompt_set = prompt_set_or_phase_idx if isinstance(prompt_set_or_phase_idx, PromptSet) else PromptSet()

        players = game_record.get_players()
        if self.player_name not in players:
            return None
        
        player_role = players[self.player_name]
        phase_type = game_record.get_phase_type(phase_idx)
        phase_count = game_record.get_phase_count()
        
        day_num = (phase_idx // 3) + 1
        
        all_player_statuses = {
            pname: game_record.get_player_status(phase_idx, pname)
            for pname in players
        }
        
        alive_players = [
            p for p, status in all_player_statuses.items()
            if status.value in {"Alive", "Mayor"}
        ]
        dead_players = [p for p, status in all_player_statuses.items() if status.value == "Dead"]
        exiled_players = [p for p, status in all_player_statuses.items() if status.value == "Exiled"]
        
        dead_info = []
        for dead_player in dead_players + exiled_players:
            role = players[dead_player]
            status_type = "killed" if dead_player in dead_players else "exiled"
            dead_info.append(f"  - {dead_player} ({role.value}): {status_type}")

        last_phase_idx = phase_idx - 1
        last_phase_type = None
        if 0 <= last_phase_idx < phase_count:
            last_phase_type = game_record.get_phase_type(last_phase_idx)

        next_phase_idx = phase_idx + 1
        next_phase_type = None
        if next_phase_idx < phase_count:
            next_phase_type = game_record.get_phase_type(next_phase_idx)
        
        content_lines = [
            f"Current Day: {day_num}",
            f"Last Phase: {last_phase_type.value if last_phase_type else 'None'}",
            f"Current Phase: {phase_type.value}",
            f"Players Alive ({len(alive_players)}): " + ", ".join(sorted(alive_players)),
        ]
        
        if next_phase_type:
            content_lines.append(f"Next Phase: {next_phase_type.value}")
        
        if dead_info:
            content_lines.append("Dead Players:")
            content_lines.extend(dead_info)
        
        if player_role == Role.WITCH:
            phase_data = game_record.get_phase_data(phase_idx)
            witch_kills = [item for item in phase_data if isinstance(item, WitchKilled)]
            witch_heals = [item for item in phase_data if isinstance(item, WitchSaved)]
            
            if witch_kills or witch_heals:
                content_lines.append("Witch Actions:")
                for kill in witch_kills:
                    content_lines.append(f"  - Killed: {kill.affected_player}")
                for heal in witch_heals:
                    content_lines.append(f"  - Healed: {heal.affected_player}")
        
        if player_role == Role.SEER:
            phase_data = game_record.get_phase_data(phase_idx)
            seer_investigations = [item for item in phase_data if isinstance(item, SeerRevealed)]
            
            if seer_investigations:
                content_lines.append("Seer Investigations:")
                for investigation in seer_investigations:
                    investigated_player = investigation.affected_player
                    investigated_role = players.get(investigated_player)
                    role_str = investigated_role.value if investigated_role else "Unknown"
                    content_lines.append(f"  - Investigated: {investigated_player} -> {role_str}")
        
        content = "\n".join(_bullet_lines(content_lines))
        
        return Ctx(
            header="Current Game State",
            content=content,
        )

    def get_topness(self) -> float:
        return 50.0


class PhaseGameContext:
    offset: int

    def __init__(self, offset: int = 0) -> None:
        self.offset = offset

    def _is_item_visible(self, item: PhaseItem, observer: PlayerName | None, observer_role: Role | None) -> bool:
        if isinstance(item, Message):
            if item.forum == Forum.VILLAGE_CHAT:
                return True
            if item.forum == Forum.WEREWOLF_CHAT:
                return observer_role == Role.WEREWOLF
            return False
            
        if isinstance(item, SystemMessage):
            return True
            
        if isinstance(item, Vote):
            if item.reason == VoteReason.KILL:
                return observer_role == Role.WEREWOLF
            if item.reason == VoteReason.EXILE:
                return True
            if item.reason == VoteReason.MAYOR:
                # Show the observer own mayor vote & hide other players votes
                return observer is not None and item.player_name == observer
            return False
            
        if isinstance(item, KillEvent | ExileEvent | MayorElected):
            return True
            
        if isinstance(item, SeerRevealed):
            return observer_role == Role.SEER
            
        if isinstance(item, WitchKilled | WitchSaved):
            return observer_role == Role.WITCH
            
        return False

    def _get_time_prefix(self, item: PhaseItem) -> str:
        ts = getattr(item, "timestamp", None)
        if ts:
            # extract HH:MM:SS from ISO string (like 2026-06-28T19:25:57Z)
            if "T" in ts:
                time_part = ts.split("T")[1]
                if "Z" in time_part:
                    time_part = time_part.replace("Z", "")
                if "." in time_part:
                    time_part = time_part.split(".")[0]
                return f"[{time_part}] "
        return ""

    def get_context(
        self,
        game_record: GameRecord,
        prompt_set_or_phase_idx: Any = None,
        phase_idx: int | None = None,
    ) -> Ctx | None:
        if phase_idx is None:
            target_phase_idx = prompt_set_or_phase_idx
            prompt_set = PromptSet()
        else:
            target_phase_idx = phase_idx
            prompt_set = prompt_set_or_phase_idx if isinstance(prompt_set_or_phase_idx, PromptSet) else PromptSet()

        phase_count = game_record.get_phase_count()
        if target_phase_idx < 0 or target_phase_idx >= phase_count:
            return None

        target_phase_idx = phase_idx - self.offset
        if target_phase_idx < 0 or target_phase_idx >= phase_count:
            return None

        phase_type = game_record.get_phase_type(target_phase_idx)
        phase_data = game_record.get_phase_data(target_phase_idx)
        players = game_record.get_players()
        day_num = (target_phase_idx // 3) + 1

        # Retrieve observer player details and chronology mode
        from wolf_llm_labeling.models import active_player_name, chronology_type
        observer = active_player_name.get()
        observer_role = players.get(observer) if observer else None
        chrono_mode = chronology_type.get()

        header = (
            "Current Phase" if self.offset == 0 else f"Phase {self.offset} ago"
        )

        content_lines = [
            f"- Day: {day_num}",
            f"- Phase: {phase_type.value}",
        ]

        if self.offset > 0:
            content_lines.append(
                f"- This phase occurred {self.offset} phase{'s' if self.offset != 1 else ''} before the current one."
            )
        else:
            content_lines.append("- This is the current phase.")

        alive_players = []
        dead_players = []
        exiled_players = []
        for player_name in players:
            status = game_record.get_player_status(target_phase_idx, player_name)
            if status.value == "Alive" or status.value == "Mayor":
                alive_players.append(player_name)
            elif status.value == "Dead":
                dead_players.append(player_name)
            elif status.value == "Exiled":
                exiled_players.append(player_name)

        content_lines.append(f"- Players alive at end of phase: {len(alive_players)}")
        if dead_players or exiled_players:
            content_lines.append("- Players no longer alive at end of phase:")
            for player_name in dead_players:
                content_lines.append(f"  - {player_name} (Dead)")
            for player_name in exiled_players:
                content_lines.append(f"  - {player_name} (Exiled)")

        # Filter phase items
        has_mayor_votes = any(isinstance(item, Vote) and item.reason == VoteReason.MAYOR for item in phase_data)
        observer_voted_mayor = any(isinstance(item, Vote) and item.reason == VoteReason.MAYOR and item.player_name == observer for item in phase_data)
        
        visible_items = []
        inserted_abstention = False
        for item in phase_data:
            if isinstance(item, MayorElected) and has_mayor_votes and not observer_voted_mayor and not inserted_abstention and observer:
                visible_items.append(SystemMessage(
                    message=f"[Only visible to you] {observer} did not vote in the mayor election.",
                    timestamp=item.timestamp
                ))
                inserted_abstention = True
                
            if self._is_item_visible(item, observer, observer_role):
                visible_items.append(item)

        if visible_items:
            # Group consecutive items of same category (messages or votes)
            steps = []
            i = 0
            n = len(visible_items)
            while i < n:
                item = visible_items[i]
                
                if isinstance(item, Message):
                    group_forum = item.forum
                    group_items = []
                    while i < n and isinstance(visible_items[i], Message) and visible_items[i].forum == group_forum:
                        group_items.append(visible_items[i])
                        i += 1
                    
                    if group_forum == Forum.WEREWOLF_CHAT:
                        title = "Conversation among players with role Werewolf:"
                    else:
                        if phase_type == PhaseType.MORNING:
                            title = "Conversation among all players for the election of a mayor:" if any("Mayor" in (msg.message or "") for msg in group_items) else "Conversation among all players:"
                        else:
                            title = "Conversation among all players:"
                    
                    formatted_items = []
                    for msg in group_items:
                        time_prefix = self._get_time_prefix(msg) if chrono_mode == "timestamp" else ""
                        formatted_items.append(f"{time_prefix}[{msg.player_name}] {msg.message}")
                        
                    steps.append({
                        "type": "group",
                        "title": title,
                        "items": formatted_items
                    })
                    
                elif isinstance(item, Vote):
                    group_reason = item.reason
                    group_items = []
                    while i < n and isinstance(visible_items[i], Vote) and visible_items[i].reason == group_reason:
                        group_items.append(visible_items[i])
                        i += 1
                    
                    if group_reason == VoteReason.KILL:
                        title = "Players with role Werewolf vote whom to kill:"
                    elif group_reason == VoteReason.EXILE:
                        title = "All players vote whom to exile:"
                    elif group_reason == VoteReason.MAYOR:
                        title = "All players vote the mayor:"
                    else:
                        title = "Players vote:"
                    
                    formatted_items = []
                    for vote in group_items:
                        time_prefix = self._get_time_prefix(vote) if chrono_mode == "timestamp" else ""
                        formatted_items.append(f"{time_prefix}{vote.player_name} voted for {vote.voted_for} ({vote.reason.value})")
                        
                    steps.append({
                        "type": "group",
                        "title": title,
                        "items": formatted_items
                    })
                    
                else:
                    desc = self._describe_phase_item(item, observer, observer_role)
                    time_prefix = self._get_time_prefix(item) if chrono_mode == "timestamp" else ""
                    steps.append({
                        "type": "single",
                        "content": f"{time_prefix}{desc}"
                    })
                    i += 1
            
            content_lines.append("\n## Phase chronology")
            for step_idx, step in enumerate(steps):
                num = step_idx + 1
                if step["type"] == "single":
                    content_lines.append(f"{num}. {step['content']}")
                elif step["type"] == "group":
                    content_lines.append(f"{num}. {step['title']}")
                    for sub_idx, sub_item in enumerate(step["items"]):
                        content_lines.append(f"   {num}.{sub_idx + 1} {sub_item}")
        else:
            content_lines.append("\nNo phase details available.")

        return Ctx(header=header, content="\n".join(content_lines))

    def _describe_phase_item(self, item: PhaseItem, observer: PlayerName | None = None, observer_role: Role | None = None) -> str:
        if isinstance(item, Message):
            return f"[{item.player_name}] {item.message}"
        if isinstance(item, SystemMessage):
            if item.message.startswith("[Only visible to you]"):
                return item.message
            return f"[Moderator] {item.message}"
        if isinstance(item, Vote):
            if item.reason == VoteReason.MAYOR:
                return f"[Only visible to you] {item.player_name} voted for {item.voted_for} ({item.reason.value})"
            return f"{item.player_name} voted for {item.voted_for} ({item.reason.value})"
        if isinstance(item, KillEvent):
            return f"{item.affected_player} was found dead."
        if isinstance(item, ExileEvent):
            if item.affected_player is None:
                return "No one was exiled."
            return f"{item.affected_player} was exiled."
        if isinstance(item, MayorElected):
            return f"{item.affected_player} was elected Mayor."
        if isinstance(item, SeerRevealed):
            return f"The Seer investigated {item.affected_player}."
        if isinstance(item, WitchKilled):
            return f"The Witch killed {item.affected_player}."
        if isinstance(item, WitchSaved):
            return f"The Witch healed {item.affected_player}."
        return str(item)

    def get_topness(self) -> float:
        return 10.0


class PhaseTrustContext:
    offset: int
    injected_trust: tuple[dict[PlayerName, Label], ...] | None
    player_name: PlayerName | None

    def __init__(
        self,
        offset: int = 0,
        injected_trust: list[dict[PlayerName, Label]] | None = None,
        *,
        player_name: PlayerName | None = None,
    ) -> None:
        if isinstance(offset, bool) or not isinstance(offset, int):
            raise TypeError("PhaseTrustContext offset must be a nonnegative integer.")
        if offset < 0:
            raise ValueError("PhaseTrustContext offset must be nonnegative.")

        self.offset = offset
        self.player_name = player_name
        self.injected_trust = None if injected_trust is None else tuple(dict(phase) for phase in injected_trust)

    def get_context(
        self,
        game_record: GameRecord,
        prompt_set_or_phase_idx: Any = None,
        phase_idx: int | None = None,
    ) -> Ctx | None:
        if phase_idx is None:
            target_phase_idx = prompt_set_or_phase_idx
            prompt_set = PromptSet()
        else:
            target_phase_idx = phase_idx
            prompt_set = prompt_set_or_phase_idx if isinstance(prompt_set_or_phase_idx, PromptSet) else PromptSet()

        target_phase_idx = target_phase_idx - self.offset
        if not 0 <= target_phase_idx < game_record.get_phase_count():
            return None

        if self.injected_trust is not None:
            if target_phase_idx >= len(self.injected_trust):
                return None
            labels = {
                target: (label,)
                for target, label in self.injected_trust[target_phase_idx].items()
            }
        else:
            if self.player_name is None:
                return None
            labels = _normalize_game_labels(game_record.get_labels(target_phase_idx).get(self.player_name, {}))

        target_contexts = []
        for target, target_labels in labels.items():
            content = _render_target_labels(target_labels)
            if content is not None:
                target_contexts.append(Ctx(header=target, content=content))

        if not target_contexts:
            return None

        return Ctx(header="Trust Labels", subsections=tuple(target_contexts))

    def get_topness(self) -> float:
        return 0.0


def _normalize_game_labels(labels: dict[PlayerName, list[Label]]) -> dict[PlayerName, tuple[Label, ...]]:
    return {target: tuple(target_labels) for target, target_labels in labels.items()}


def _render_score(name: str, score: Score | None) -> str | None:
    if score is None:
        return None
    return f"{name}: trust {score.trust}/7, confidence {score.confidence}/3"


def _render_label(label: Label) -> str | None:
    lines = [
        line
        for line in (
            _render_score("Alignment", label.trust_scores.alignment),
            _render_score("Information", label.trust_scores.information),
            _render_score("Consistency", label.trust_scores.consistency),
        )
        if line is not None
    ]
    reasoning = label.reasoning.strip()
    if reasoning:
        lines.append(f"Reasoning: {reasoning}")
    return "\n".join(lines) if lines else None


def _render_target_labels(labels: tuple[Label, ...]) -> str | None:
    rendered_labels = [rendered for label in labels if (rendered := _render_label(label)) is not None]
    if not rendered_labels:
        return None
    if len(rendered_labels) == 1:
        return rendered_labels[0]
    return "\n\n".join(f"Label {index}:\n{rendered}" for index, rendered in enumerate(rendered_labels, start=1))


def _render_trust_scores_no_rationale(scores: TrustScores) -> str | None:
    lines = [
        line
        for line in (
            _render_score("Alignment", scores.alignment),
            _render_score("Information", scores.information),
            _render_score("Consistency", scores.consistency),
        )
        if line is not None
    ]
    return "\n".join(lines) if lines else None


class InnerTrustVoiceContext:
    '''
        This context returns the scores of an inner trust voice for all players (except self).
        The inner voice is provided a custom trust context.
    '''

    def __init__(self, inner_voice: InnerVoice, inner_voice_context: ContextProvider) -> None:
        self.inner_voice = inner_voice
        self.inner_voice_context = inner_voice_context

    def get_context(
        self,
        game_record: GameRecord,
        prompt_set_or_phase_idx: Any = None,
        phase_idx: int | None = None,
    ) -> Ctx | None:
        if phase_idx is None:
            target_phase_idx = prompt_set_or_phase_idx
            prompt_set = PromptSet()
        else:
            target_phase_idx = phase_idx
            prompt_set = prompt_set_or_phase_idx if isinstance(prompt_set_or_phase_idx, PromptSet) else PromptSet()

        from wolf_llm_labeling.models import active_player_name

        observer = active_player_name.get()
        players = game_record.get_players()
        iv_context = self.inner_voice_context.get_context(game_record, prompt_set, target_phase_idx)

        player_sections = []
        for player in players:
            if player == observer:
                continue
            scores = self.inner_voice.ask(player, iv_context, game_record, prompt_set, phase_idx)
            content = _render_trust_scores_no_rationale(scores)
            if content is not None:
                player_sections.append(Ctx(header=player, content=content))

        if not player_sections:
            return None

        return Ctx(header="Inner Trust Voice Advice", subsections=tuple(player_sections))

    def get_topness(self) -> float:
        return 0.0
