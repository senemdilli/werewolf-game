# Data Analysis — Werewolf Trust Data Scientist Agent

Analyzes how **LLM trust labeling behaves compared to human trust labeles** on the same
werewolf games. Humans annotate trust in the web game;
the [labeling engine](../llm-labeling/) produces LLM annotations of the same games.
This package loads both into one unified table and exposes
analysis tools to an LLM orchestrator the user can query in natural language.

---

## Setup

Requires [uv](https://docs.astral.sh/uv/) (Python 3.12 is fetched automatically) as well as a [.env](/data-analysis/.env) file with an Ollama API key(see [.env.example](data-analysis/.env.example)).

```bash
cd data-analysis
make install        # = uv sync --extra dev
```

## Quickstart

```python
from data.dataset import load_dataset
from data.filters import FilterSpec, apply_filters

df = load_dataset(
    "../results/game-records",              # human labels + game events exports
    "../results/llm-labeling",             # labeling engine outputs (optional)
    cache_dir="../results/data-analysis/cache", # parquet cache (optional)
)

# Average alignment trust received by werewolves, human labels only
spec = FilterSpec(sources=["human"], trust_types=["alignment"], target_teams=["WEREWOLVES"])
apply_filters(df, spec)["score_norm"].mean()
```

Run the tests:

```bash
uv run pytest
```

The suite includes integration tests against the real exports in
`../results/game-records`; they skip automatically when that directory is absent.

## Asking the agent

The orchestrator answers natural-language questions by driving the analysis
tools with a chat model on the SNET Ollama server. Copy `.env.example` to
`.env` and set `OLLAMA_API_KEY` (note: the model is configured via
`AGENT_MODEL`, default `gemma4:26b`), then:

```bash
uv run python main.py agent "How does human trust in werewolves evolve across phases?"
uv run python main.py agent        # interactive: type questions, empty line exits
make run                           # same as the interactive form
```

Answers take ~30–60 s (usually several tool calls). Plots the agent creates
land in `../results/data-analysis/plots/`. Run with `LOG_LEVEL=DEBUG` to watch every tool call
and its arguments — the agent often gets a filter wrong on the first try and
recovers from the tool's error message; that loop is by design (see
"Errors are prompts" below).

---

## Input data

Three JSON export types feed the dataset. Files are recognized by **content**
(which top-level keys they have), not by filename, and are joined to each other
by `game_id`.

| Input | Produced by | Shape |
|---|---|---|
| Game events (`game-<room>-<id>.json`) | web game export | `events[]`: chat, votes, night actions — the ground-truth record |
| Human labels (`game-<room>-<id>-labels.json`) | web game export | `rounds[] → checkpoints[] → labels[]`: observer → targets with 3 trust dimensions |
| LLM run (`<player>-<uuid>.json`) | labeling engine | one file per (game, labeled player, run): `phases[] → labels{target}` + run metadata |

`data/dataset.py` scans a directory of game records (non-recursive) and an
optional LLM results directory (recursive), and warns about files it cannot
match or parse.

## The unified table

Everything downstream works on one long-format DataFrame:
**one row per (game, source, run, observer, target, phase, trust dimension)**.
Built by `build_dataset()`, cached by `load_dataset()` (parquet, invalidated
whenever any input file changes — but **not** when loader code changes; after
editing loaders, `rm -rf ../results/data-analysis/cache`).

One cleaning step happens at build time: **`observer == target` rows are
dropped** (with a warning naming the run files). The game never asks players
to rate themselves, so self-labels can only be labeling-engine glitches — the
LLM occasionally includes itself in its own target list and rates itself
NEUTRAL, which would dilute means and put ghost values on heatmap diagonals.

| Column(s) | Meaning |
|---|---|
| `game_id`, `room_code`, `game_mode`, `winner`, `exported_at` | game metadata |
| `source` | `"human"` or `"llm"` |
| `run_id` | LLM result file stem (e.g. `Blue-99c55270`); `"human"` for human rows |
| `observer`, `observer_role`, `observer_team`, `observer_alive` | who gave the trust score |
| `target`, `target_role`, `target_team`, `target_alive` | who received it |
| `round`, `checkpoint`, `phase_idx` | when in the game (see phase alignment) |
| `trust_type` | canonical dimension: `alignment` \| `information` \| `consistency` |
| `score_raw`, `scale`, `score_norm` | trust score: original value, its scale, and normalized [0, 1] |
| `confidence_raw`, `confidence_scale`, `confidence_norm` | confidence: 1–3 ordinal and normalized [0, 1] |
| `reasoning`, `created_at` | free-text rationale, annotation time |
| `model`, `inner_voice_model`, `experiment`, `temperature`, `trust_scale_mode`, `formatter`, `experiment_args`, `max_phases`, `context_as_tool` | LLM run configuration (`None` on human rows) |

Roles/teams come from the game events export: `WEREWOLF → WEREWOLVES`, every
other role → `VILLAGERS`.

### Trust dimensions

The sources name their dimensions differently; both are mapped to canonical
names (`data/models/trust_metric.py`):

| Human export | LLM output | Canonical |
|---|---|---|
| `alignment` | `alignment` | `alignment` |
| `information` | `strategic` | `information` |
| `consistency` | `consistency` | `consistency` |

Targets with a `null` dimension are skipped (no row).

### Scales and normalization

`data/normalization.py`. Raw values are always kept next to the normalized
ones — distribution-shape analyses (e.g. "LLMs rate more extremely than
humans") must use `score_raw` + `scale`, never normalized means.

| Source | Trust scale | Confidence |
|---|---|---|
| human | integer 1–7 | `LOW / MEDIUM / HIGH` → 1–3 |
| LLM likert mode (both variants) | integer 1–7 (stored next to the likert string) | 1–3 |
| LLM numeric mode | integer 1–100 | 1–3 |

`score_norm = (raw - min) / (max - min)`, likewise for confidence. Old LLM
result files without `trust_scale_mode` are inferred: any score above 7 means
the 1–100 scale.

### Phase alignment

Human labels are keyed by `(round, checkpoint)`; LLM outputs by a flat
`phase_idx`. The labeling engine derives its phase list from system messages
in the game record — `data/phase_alignment.py` reproduces that construction
from the events export, so the two keyings translate 1:1:

| Checkpoint | Trigger message | Engine phase name |
|---|---|---|
| `BEFORE_DISCUSSION` | "Dawn breaks. …" | MORNING |
| `BEFORE_VOTING` | "Voting begins." | DAY |
| `AFTER_VOTING` | "The village voted …" / tie | EVENING |

One quirk (mirrored from the engine): system messages occurring *after* a
round's vote result count toward the next round. The module also tracks which
players are dead at each phase (from death/elimination announcements), which
feeds the `observer_alive` / `target_alive` columns.

> If the engine's phase construction changes
> (`llm-labeling/src/wolf_llm_labeling/game_records.py`), this module must be
> updated with it — the real-game tests in `tests/test_phase_alignment.py`
> guard against divergence.

## Filtering

`data/filters.py` defines `FilterSpec`, the single filter vocabulary every
analysis tool (and eventually the orchestrator LLM) uses. List fields mean
"match any"; `None` means no constraint. String matching on teams/roles/types
is case-insensitive.

```python
FilterSpec(
    # game-level
    game_ids=[...], room_codes=[...], game_modes=[...], winners=[...],
    # source / run
    sources=["human"], run_ids=[...],
    # perspective: trust GIVEN by X -> observer_*; trust RECEIVED by X -> target_*
    observers=[...], targets=[...],
    observer_teams=["WEREWOLVES"], target_teams=[...],
    observer_roles=[...], target_roles=[...],
    exclude_self=True,      # drop observer == target rows
    alive_only=True,        # both observer and target alive at that phase
    # time within the game
    trust_types=["alignment"], checkpoints=["BEFORE_VOTING"],
    round_min=1, round_max=3, phase_idx_min=0, phase_idx_max=8,
    # LLM experiment configuration
    models=[...], experiments=["a"], trust_scale_modes=["likert"],
    temperature_min=0.0, temperature_max=0.5, context_as_tool=False,
)
```

```python
apply_filters(df, spec)  # -> filtered DataFrame
```

### Semantics worth knowing

- **LLM-config fields constrain LLM rows only.** `models`, `experiments`,
  `trust_scale_modes`, `temperature_min/max`, and `context_as_tool` never drop
  human rows (humans have no run configuration). So
  `FilterSpec(experiments=["b"])` means "humans + the experiment-b LLM runs" —
  exactly what a human-vs-LLM comparison pinned to one engine config needs.
  Add `sources=["llm"]` to get only the LLM side.
- **Excluding werewolf-produced labels**: there is no negation syntax; use the
  complement. `observer_teams=["VILLAGERS"]` keeps only labels *given by* the
  village side (seer and witch included — they're on the villager team).
  Werewolves know all roles, so their "trust" labels are strategic theater;
  the villager-observers slice is the honest-trust one. Mirror question:
  `target_teams` filters by who *received* the trust.
- **Lenient where unambiguous, loud where not.** Written for an LLM caller:
  singular field names (`room_code=...`) and bare strings (`"5NOHGS"` instead
  of `["5NOHGS"]`) are accepted and normalized, but an unknown field is a
  validation error, never silently ignored.

### Errors are prompts

Tool error messages are written for the orchestrator LLM, whose next move is
determined by the error text. An empty slice therefore explains *why* it is
empty ("`'5NOHGS' is not a game_id; use room_codes instead`", "matches no
room_code (examples: ...)", or "the combination is too narrow; drop one
constraint"). Observed effect: the same misfiled heatmap request went from
10 minutes of blind retries to a one-retry recovery. When changing tools,
keep error messages actionable — say what to do, not just what failed.

## Project layout

```
data-analysis/
├── agent/                  # LLM orchestrator: natural-language queries -> tool calls
├── analysis/               # generated artifacts: cache/, plots/ (gitignored)
├── contracts/tool_output.py    # ToolOutput contract all tools return
├── core/                   # settings (.env) + logging
├── data/
│   ├── models/             # pydantic models mirroring the three export schemas
│   ├── loaders/            # per-source file loaders -> unified rows
│   ├── normalization.py    # scale mappings -> [0, 1]
│   ├── phase_alignment.py  # checkpoint <-> phase_idx + death tracking
│   ├── filters.py          # FilterSpec + apply_filters
│   └── dataset.py          # build_dataset / load_dataset (parquet cache)
├── tools/
│   ├── base_tool.py        # BaseTool: run(**kwargs) -> ToolOutput, as_langchain_tool()
│   ├── slicing.py          # shared slice/describe/match helpers (MATCH_KEYS, matched_cells, ...)
│   ├── compare_tool.py     # compare_data: slice comparison / evaluation
│   ├── plot_tool.py        # plot: PNG + caption + underlying numbers
│   ├── delta_tool.py       # delta_tool: matched-cell delta between 2 sources or 2 trust types
│   └── correlation_tool.py # correlation_tool: extremity comparison + extremity/confidence correlation
└── tests/                  # unit tests on fixtures + integration on real exports
```

## Analysis tools

All four tools operate on the unified table and accept `FilterSpec`s; run them
from the CLI with JSON params (same interface the phase-3 orchestrator will use):

```bash
# compare two slices: human vs LLM on one game, broken down by trust dimension
uv run python main.py tool compare_data --params '{
  "filters_a": {"sources": ["human"], "room_codes": ["5NOHGS"]},
  "filters_b": {"sources": ["llm"],   "room_codes": ["5NOHGS"]},
  "group_by": ["trust_type"], "correlate": true}'

# plot human vs LLM alignment trust across the phases of one game
uv run python main.py tool plot --params '{
  "filters": {"room_codes": ["5NOHGS"], "trust_types": ["alignment"]},
  "kind": "line_per_phase"}'

# delta between alignment and information trust, by round
uv run python main.py tool delta_tool --params '{
  "filters": {"sources": ["human"]},
  "compare": "trust_type", "value_a": "alignment", "value_b": "information",
  "group_by": ["round"]}'

# how extreme is LLM labelling vs human, and does confidence track extremity?
uv run python main.py tool correlation_tool --params '{
  "filters_a": {"sources": ["human"]}, "filters_b": {"sources": ["llm"]}}'
```

**`compare_data`** — one slice (`filters_a` only) → descriptive stats: n, mean,
raw histogram, extremeness index (0 = all midpoint, 1 = all endpoints). Two
slices → delta of means plus, in *matched* mode (cells identical in
game/observer/target/phase/dimension), signed delta, MAE, Spearman,
quadratic-weighted kappa, and a Wilcoxon test; in *independent* mode
Mann-Whitney U and KS tests. `mode="auto"` picks matched when the specs differ
only on source-like fields. `group_by` yields a per-value breakdown;
`correlate=true` adds the score-extremity ↔ confidence Spearman per slice.
Empty slices and n below 5 come back as errors/warnings, never silent numbers.

**`plot`** — renders the slice to `../results/data-analysis/plots/*.png` and returns the
aggregated values behind the figure (the orchestrator can't see images).
Kinds: `line_per_phase` (one game), `line_per_game` (chronological),
`histogram` (raw scores per hue — the extremeness picture), `box`, `scatter`
(extremity vs confidence), `heatmap` (observer×target matrix, one game).
`hue` defaults to `"source"` so human vs LLM overlay; `use_raw=true` is
rejected when the slice mixes scales.

Charts are self-describing: trust axes and the heatmap colorbar are labeled
with the seven likert level names (`VERY_LOW_TRUST` … `NEUTRAL` …
`VERY_HIGH_TRUST`) instead of normalized numbers; heatmap axes annotate each
player's role (`Blue (W)`, `Lime (Wi)`, `Beige (S)`, `... (V)`); and every
figure prints its active filters bottom-right (also appended to the returned
caption), so any PNG can be traced back to the exact slice it shows.
Confidence plots keep numeric axes — likert trust words would be wrong there.

**`delta_tool`** — `score_a - score_b` between two values of `compare`:
`compare="source"` (`value_a`/`value_b` in `{"human","llm"}`) or
`compare="trust_type"` (`value_a`/`value_b` in
`{"alignment","information","consistency"}`), matched on
game/room_code/observer/target/phase (and whichever of source/trust_type
isn't the axis being compared). `group_by` breaks the delta down by round,
phase_idx, checkpoint, team/role columns, or `room_code` (carrying
`exported_at` along, so per-game deltas can be sorted chronologically).
Built on `tools/slicing.py`'s `matched_cells`, same identity keys as
`compare_data`.

**`correlation_tool`** — compares labelling *extremity* between two slices
(`filters_a` vs `filters_b`) and correlates extremity with confidence within
each slice. `extremity = |score_norm - 0.5| * 2` (0 = midpoint, 1 = either
endpoint) — the fold-to-endpoint distance that makes "1/7 and 7/7 are both
extreme" one comparable number, and the correlation captures "humans are
only confident at the extremes, LLMs may not be." Reports per-slice
`mean_extremity`, `frac_at_extreme`, and `extremity_confidence_spearman`; the
delta in extremity between slices (independent Mann-Whitney U, and on
matched cells a paired Wilcoxon); and an optional `group_by` breakdown. Also
built on `tools/slicing.py`'s `matched_cells`, matching on `extremity`
instead of raw `score_norm`.

## Adding an analysis tool

Subclass `BaseTool`; the langchain conversion is derived from your `run`
signature:

```python
from contracts.tool_output import ToolOutput
from tools.base_tool import BaseTool
from tools.slicing import explain_empty_slice, slice_df

class MyTool(BaseTool):
    name = "my_tool"
    description = "What the orchestrator should know about this tool."

    def run(self, filters: FilterSpec) -> ToolOutput:
        rows = slice_df(self._df, filters)
        if rows.empty:
            return ToolOutput(success=False, source=self.name,
                              error=explain_empty_slice(self._df, filters))
        return ToolOutput(success=True, source=self.name, data=..., metadata={"n_rows": len(rows)})
```

Conventions: tools are pure functions over the unified table (no LLM calls
inside), always return `ToolOutput`, and report row counts in `metadata` so
the orchestrator notices empty filter results. If your tool needs to compare
two slices or join on "same cell" (as `compare_data`, `delta_tool`, and
`correlation_tool` all do), build on `tools/slicing.py`'s `slice_df`,
`matched_cells`, `matchable`/`differing_fields` rather than re-deriving cell
identity by hand — that's the one place `MATCH_KEYS` (including `room_code`)
is defined, so tools don't drift out of sync on what counts as "the same
annotation" measured twice.
