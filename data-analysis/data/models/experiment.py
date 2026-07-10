"""One LLM labeling run output file (`<player>-<uuid>.json`).

Older result files predate some metadata fields (e.g. `trust_scale_mode`,
`temperature`), so everything beyond the identifying fields is optional.
"""

from typing import Any

from pydantic import BaseModel

from data.models.experiment_phase import LLMPhase


class LLMRun(BaseModel):
    game_id: str
    game_file: str | None = None
    player_name: str  # the observer whose perspective was labeled
    run_id: str | None = None  # derived from the file name by the loader
    trust_scale_mode: str | None = None  # "numeric" | "likert"
    models: dict[str, str] = {}
    prompts: dict[str, Any] | None = None
    time: str | None = None
    experiment: str | None = None
    formatter: str | None = None
    experiment_args: str | None = None
    temperature: float | None = None
    max_phases: int | None = None
    context_as_tool: bool | None = None
    total_phases: int | None = None
    alive_phases: int | None = None
    phases: list[LLMPhase] = []

    @property
    def primary_model(self) -> str | None:
        return self.models.get("primary_model")

    @property
    def inner_voice_model(self) -> str | None:
        return self.models.get("inner_voice_model")
