# Artifact Appendix

Paper title: **AI Agents Playing a Trust Game**

These instructions are written for someone who wants to reproduce or reuse the
artifact in the future, not only for an artifact reviewer.

## Description

This artifact accompanies the paper *AI Agents Playing a Trust Game* (IoSL
Project Group 7, TU Berlin, 2026; C. Mosler, T. Ax, M. Reich, S. Dilli,
T. Baumann, I. Yilmaz, N. N. Fickel, A. Gelecek, C. U. Jhurree). It is the
project mono-repository and contains the complete, runnable research pipeline
together with the collected data, so the paper can be reproduced end to end.

The artifact is organized into the three software modules described in
Section 3 of the paper, plus the data:

- `werewolf-game/`: the Next.js/TypeScript web platform on which the human games
  were played and trust-labeled, including the WebSocket game server, the
  in-game labeling UI, and the Admin Research Panel used to export game records.
- `llm-labeling/`: the LLM Labeling Engine (record parser, compositional context
  providers, prompt sets, inner voice, and the labeling runner), the six
  experiment definitions A to F, and the archived experiment outputs under
  `llm-labeling/results/`.
- `data-analysis/`: the Data Analysis Agent, comprising the unified human/LLM
  dataset builder, the filter vocabulary, the analysis tools (compare, plot,
  delta, correlation), and the LLM orchestrator over them.
- `results/game-records/`: the pseudonymized human dataset, i.e. per-game event
  exports (CSV and JSON) and human trust labels (JSON) for the 31 recorded
  games. Games with incomplete voting data are prefixed `MISSING_VOTING_` and
  are excluded from analysis.
- `design/` and `docs/`: design documents (rules, trust-label taxonomy) and the
  export-format reference.

The artifact is hosted at
<https://git.tu-berlin.de/snet-internal/wolf-iosl-2026>. A central `README`
links to a dedicated `README` for each module.

### Security/Privacy Issues and Ethical Concerns

The artifact poses no security risk to the evaluator's machine: it disables no
security mechanism (no firewall or ASLR changes) and ships no exploit, malware,
or vulnerable code. Two points warrant care. First, the dataset consists of real
play-session data (chat messages, votes, and trust judgments); it is
pseudonymized to randomized color display names (for example `Blue`, `Lime`),
and the mapping to real identities is not part of the artifact. Second, the game
platform reads secrets from environment variables: the Admin Research Panel is
gated by `ADMIN_SECRET`, and the default `ADMIN_SECRET` in
`werewolf-game/docker-compose.yml` must be changed for any non-local deployment.
The optional voice input streams audio to a third-party service (Deepgram) only
when a player chooses to use it; it is not needed for reproduction.

## Basic Requirements

### Hardware Requirements

1. Minimal requirements: the Werewolf game platform and the data analysis can
   run on a laptop (no special hardware requirements). Re-running the LLM
   labeling experiments additionally requires access to an LLM inference
   endpoint: either an Ollama server able to serve the paper's models (up to
   `mistral-large:123b`, i.e. a GPU server-class machine), or any
   OpenAI-compatible endpoint (for example LM Studio) with a smaller local model
   for functional testing. The paper's runs used the TU Berlin SNET Ollama GPU
   server (`gpu.snet.tu-berlin.de/echelon/ollama`), access to which is
   restricted to TU Berlin.
2. Hardware used in the paper: all experiments (including those archived in the
   results folder) were orchestrated from a Windows 11 PC (Intel i9-11900K CPU,
   32 GB RAM, 2 TB storage). Model inference itself ran on the SNET inference
   server (TU Berlin).

### Software Requirements

1. OS: development and the reported runs used Windows 11; the stack is
   OS-independent and also runs on Linux (for example Ubuntu 24.04) and macOS.
   There are no OS-specific code paths.
2. OS packages: `git`; Docker (>= 24) with Docker Compose; for the Python
   modules, `uv` (which fetches Python 3.12 automatically) and a Python >= 3.14
   interpreter with `pip`.
3. Artifact packaging: the game platform is containerized with Docker Compose
   using three services, an application service (`node:20-alpine` base image),
   `postgres:16-alpine`, and `redis:7-alpine`.
4. Interpreters: LLM Labeling Engine requires Python >= 3.14; the Data Analysis
   Agent uses Python 3.12 (pinned via `data-analysis/.python-version`, managed by
   `uv`).
5. Packages: labeling-engine dependencies are listed in
   `llm-labeling/requirements.txt` (and `llm-labeling/pyproject.toml`); analysis
   dependencies are pinned in `data-analysis/uv.lock` (pandas, SciPy, matplotlib,
   pyarrow, LangChain/LangGraph, pydantic); the game platform's Node dependencies
   are pinned in `werewolf-game/package-lock.json`.
6. ML models: the labeling runs used the Ollama-served open-weight models
   `gemma4:31b`, `qwen3.6:35b`, and `mistral-large:123b`, with `gemma4:12b` for
   local smoke testing. The comprehension benchmark (Section 5.2) used
   `gemma4:31b` as the answer model and
   `mistral-large:123b-instruct-2411-q6_K` as the judge. The analysis agent
   defaults to `gemma4:26b` (`MODEL_NAME` in `data-analysis/.env`). Any
   tool-calling chat model works as a dummy for functional evaluation.
7. Datasets: fully contained in the artifact under `results/game-records/`
   (31 recorded games). JSON Schemas for the three file types (game events, human
   labels, LLM label output) are provided in `llm-labeling/schemas/`, and
   synthetic fixtures demonstrating the formats are in
   `data-analysis/tests/fixtures/`.

### Estimated Time and Storage Consumption

- Environment setup: about 20 human-minutes.
- A full functional pass (Experiments 1 to 3 below): about 30 human-minutes plus
  20 to 90 compute-minutes, dominated by the LLM endpoint.
- Reproducing a single labeling run (one game, one experiment, all 8 player
  perspectives) takes 20 to 90 compute-minutes depending on the model:
  `mistral-large:123b` is slowest, while `gemma4:31b` and `qwen3.6:35b` run in
  20 to 50 minutes. One game yields on the order of 50 to 80+ LLM inferences
  (roughly 4-5 alive phases per player, times 8 players, times at least 2 calls),
  and more with Inner Voice Variant 2.
- Building the dataset and reproducing the tables (Experiment 2) runs in under
  5 compute-minutes.
- Total artifact disk footprint, including all archived results, is under 1 GB.

## Environment

### Set up the environment

Clone the repository and set up the three modules. The game platform and each
Python module are independent; you only need the module(s) for the experiments
you want to run.

```bash
git clone https://git.tu-berlin.de/snet-internal/wolf-iosl-2026.git
cd wolf-iosl-2026

# 1) Werewolf game platform (Docker); app served on http://localhost:3001
cd werewolf-game
# ADMIN_SECRET has a default in docker-compose.yml; override it for any shared
# deployment. DEEPGRAM_API_KEY is optional and only enables voice input.
ADMIN_SECRET=change-me docker compose up --build -d

# 2) LLM Labeling Engine (Python >= 3.14)
cd ../llm-labeling
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
printf "OLLAMA_API_KEY=<your key>\n" > .env

# 3) Data Analysis Agent (uv installs Python 3.12 automatically)
cd ../data-analysis
make install           # = uv sync --extra dev
cp .env.example .env    # set OLLAMA_API_KEY; MODEL_NAME defaults to gemma4:26b
```

Expected result: the game platform is reachable at <http://localhost:3001>; the
two Python environments install without errors.

### Testing the Environment

Three quick checks confirm the three modules are set up correctly.

Game platform: open <http://localhost:3001>; the landing page loads and a room
can be created (use Sandbox Mode with bots to advance a game without eight human
players).

Analysis package: from `data-analysis/`, run the test suite (unit tests plus
integration tests against the real exports in `results/game-records/`); all tests
must pass.

```bash
uv run pytest
```

Labeling engine: a one-phase dry run against any endpoint exercises the full
record-parsing, context, and LLM loop.

```bash
python ./src/wolf_llm_labeling/main.py \
  ../results/game-records/game-44UT6Y-d59e923e-labels.json \
  ../results/game-records/game-44UT6Y-d59e923e.csv \
  --primary-model any --ollama-url <ENDPOINT> \
  --experiment a --player-name Blue --max-phases 1
```

Expected output: one result JSON and one Markdown trace under
`results/llm-labeling/a/game-44UT6Y-.../`.

## Artifact Evaluation

### Main Results and Claims

#### Main Result 1: LLM trust tracks human phase trends but is model-dependent

On matched games, the per-phase mean alignment-trust of the LLMs follows the
human phase trend, but the level is biased by model and size: Gemma trusts
others less, Mistral trusts almost everyone highly, and Qwen is closest to the
human values in `game-5NOHGS`; in `game-UBY0T7` Gemma is closer to the (lower)
human values than Qwen. Independent variables: model (and phase); dependent
variable: mean alignment-trust. This is reported in Section 5.1, Table 2
(`game-5NOHGS`) and Table 3 (`game-UBY0T7`). Reproducible via
[Experiment 1](#experiment-1-generate-llm-trust-labels) followed by
[Experiment 2](#experiment-2-build-the-unified-dataset-and-reproduce-the-tables).

#### Main Result 2: Adding own previous trust scores stabilizes and calibrates labels

Providing the player's own previous trust scores (Experiment B, memory cutoff 3)
compared to chat logs only (Experiment A, cutoff 0) reduces phase-to-phase
fluctuation, moves the LLM means slightly closer to the human mean in nearly all
cases, and makes the LLMs more confident. Independent variable: context
condition (Experiment A versus B); dependent variables: mean alignment-trust and
mean confidence. Reported in Section 5.1 (Tables 2 and 3) and Appendix D.1
(confidence, Tables 9 and 10). Reproducible via
[Experiment 1](#experiment-1-generate-llm-trust-labels) and
[Experiment 2](#experiment-2-build-the-unified-dataset-and-reproduce-the-tables).

#### Main Result 3: The Human Historic Inner Voice moves labels toward human values

In Experiments D to F (Variant 2, the inner voice exposed as a tool), the Human
Historic Inner Voice tends to pull alignment-trust closer to the human values,
most clearly for Experiment D versus A; the number of inner-voice tool calls
varies by model and experiment (Qwen calls more often than Gemma, and calls are
most frequent in Experiment D). Independent variables: inner-voice experiment
(D, E, F) and model; dependent variables: mean alignment-trust and tool-call
count. Reported in Section 5.1 (Table 4) and Appendix D.3 (Table 12).
Reproducible via [Experiment 1](#experiment-1-generate-llm-trust-labels) (the
D to F runs) and
[Experiment 2](#experiment-2-build-the-unified-dataset-and-reproduce-the-tables).

#### Main Result 4: Low sampling temperature induces reasoning loops

At temperature 0.0 the labeling models spend longer on reasoning and can enter
repetitive reasoning loops that exceed the context or token limit and disrupt
labeling; the effect is far less frequent at higher temperatures, so all
reported results use temperature 0.5. Independent variable: sampling
temperature; dependent variables: reasoning length and loop occurrence. Reported
in Section 5.1. Reproducible via
[Experiment 1](#experiment-1-generate-llm-trust-labels) run at 0.0 versus 0.5.

### Experiments

#### Experiment 1: Generate LLM trust labels

- Time: about 5 human-minutes + 20 to 90 compute-minutes per (game, experiment,
  model).
- Storage: under 100 MB.

From `llm-labeling/`, run the engine for a recorded game and experiment variant.
Examples for Experiment A (chat only, cutoff 0), Experiment B (chat plus own
previous scores, cutoff 3), and Experiment D (chat plus Human Historic Inner
Voice as a tool):

```bash
# Experiment A
python ./src/wolf_llm_labeling/main.py \
  ../results/game-records/game-5NOHGS-b57eee98-labels.json \
  ../results/game-records/game-5NOHGS-b57eee98.csv \
  --primary-model gemma4:31b --ollama-url <ENDPOINT> \
  --experiment a --prompt-set prompts/prompt_sets/pimped.json \
  --cutoff 0 --temperature 0.5 --parallel 4

# Experiment B
python ./src/wolf_llm_labeling/main.py \
  ../results/game-records/game-5NOHGS-b57eee98-labels.json \
  ../results/game-records/game-5NOHGS-b57eee98.csv \
  --primary-model gemma4:31b --ollama-url <ENDPOINT> \
  --experiment b --prompt-set prompts/prompt_sets/pimped.json \
  --cutoff 3 --temperature 0.5 --parallel 4

# Experiment D (inner voice as tool, Human Historic voice, cutoff 3)
python ./src/wolf_llm_labeling/main.py \
  ../results/game-records/game-UBY0T7-140e8697-labels.json \
  ../results/game-records/game-UBY0T7-140e8697.csv \
  --primary-model gemma4:31b --ollama-url <ENDPOINT> \
  --experiment d --variant 2 --inner-voice-type human \
  --cutoff 3 --prompt-set prompts/prompt_sets/pimped.json \
  --temperature 0.5 --parallel 4
```

Expected result: one JSON result and one Markdown trace per player under
`results/llm-labeling/<experiment>/<game>/<model>/`, schema-identical to the
archived runs. To reproduce Main Result 4, additionally run one configuration
with `--temperature 0.0` and inspect the trace for elongated or looping
reasoning. Full-matrix reproduction is available via `python run_all.py` or the
config-driven `src/wolf_llm_labeling/batch_runner.py`. Note that hosted LLM
outputs at temperature above 0 are not bit-reproducible; phase-mean scores are
expected to vary by a few tenths of a point. Supports Main Results 1 to 4.

#### Experiment 2: Build the unified dataset and reproduce the tables

- Time: about 5 human-minutes + under 5 compute-minutes.
- Storage: negligible.

From `data-analysis/`, load the human exports together with the archived (or
freshly generated) LLM runs into the unified table and aggregate per-phase
alignment-trust means per experiment. Filter by `room_code` for a specific game
(for example `5NOHGS` for Table 2, `UBY0T7` for Table 3); use `confidence_raw`
instead of `score_raw` to reproduce the confidence tables in Appendix D.1.

```bash
uv run python - <<'PY'
from data.dataset import build_dataset
df = build_dataset("../results/game-records",
                   "../llm-labeling/results/llm-labeling")
g = df[(df.room_code == "5NOHGS") & (df.trust_type == "alignment")]
piv = g.pivot_table(index="phase_idx",
                    columns=["source", "experiment"],
                    values="score_raw", aggfunc="mean")
print(piv.round(2))
PY
```

Expected result: a per-phase table of mean alignment-trust for the human source
and for each LLM experiment, matching the values in Tables 2 and 3 of the paper
(and the confidence values in Tables 9 and 10 when using `confidence_raw`). The
same unified table underlies the delta and correlation tools. Supports Main
Results 1 to 3.

#### Experiment 3: Query the Data Analysis Agent

- Time: about 5 human-minutes + 1 to 2 compute-minutes per question.
- Storage: negligible.

From `data-analysis/`, ask the analysis agent a natural-language question; it
answers by orchestrating the analysis tools over the unified dataset.

```bash
uv run python main.py agent \
  "How does human trust in werewolves evolve across phases?" \
  --game-records ../results/game-records \
  --llm-results ../llm-labeling/results/llm-labeling
# equivalently: make run
```

Expected result: the agent answers in natural language after several tool calls
(about 30 to 60 seconds); any plots it produces are written to the analysis
output directory. Demonstrates the Data Analysis Agent contribution.

## Limitations

The human data collection itself (real eight-player play sessions) is not
reproducible from the artifact; the platform is provided so that new sessions can
be run, but the paper's dataset of 31 games is fixed. Exact LLM labels are not
bit-reproducible, because the hosted open-weight models are sampled at
temperature 0.5; the archived result JSONs, prompts, and Markdown traces make the
paper's concrete numbers verifiable, and fresh runs reproduce the results
qualitatively (phase trends, the A-versus-B stabilization, and the inner-voice
effect), typically within a few tenths of a point per phase mean. The
comprehension benchmark of Section 5.2 (objective 87.5 percent, speculative
70.8 percent) was produced with an ad hoc leave-one-phase-out setup and does not
ship as a standalone script, so its exact numbers are not reproducible from a
single command, although the underlying labeling engine and game records are
provided. The SNET GPU server is restricted to TU Berlin; evaluators without
access substitute any Ollama or OpenAI-compatible endpoint, which changes only
runtimes and the specific model. Because of the long inference times, several
evaluation tables report a subset of games (primarily `game-5NOHGS`,
`game-44UT6Y`, and `game-UBY0T7`) rather than all 31; these are illustrative, and
the artifact should still be evaluated for functional and reproducible badges,
since every reported cell is regenerable with the commands above.

## Notes on Reusability

The pipeline is modular and reusable beyond this paper. The game platform can
record new human datasets (Classic or the stricter Arena mode, configurable
timers, witch self-heal, sandbox bots) without code changes and exports them in
the documented CSV/JSON formats. The LLM Labeling Engine is game-record-driven:
new experiments are single Python files under `llm-labeling/src/experiments/`;
prompts, tool descriptions, and response formats are swappable via prompt-set
JSONs and the `--prompt-set` flag; the context depth is tuned with `--cutoff`;
any Ollama- or OpenAI-compatible model can be plugged in with `--primary-model`
and `--ollama-url`; and new inner voices only need to implement the predefined
Python interface. The Data Analysis Agent ingests any files matching the
published JSON Schemas, exposes a single declarative filter vocabulary that new
tools reuse, and registers new analysis tools through its tool registry, so the
natural-language agent can drive them without further changes.
