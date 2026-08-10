# Artifact Appendix

Paper title: **AI Agents Playing a Trust Game**

## Description

This artifact appendix guides the user to run and reuse the project later.

The repository has three code folders and the data. The pipeline and its three
modules are described in Section 3 of the paper, and the system architecture is
drawn in Appendix B (Figure 1).

- `werewolf-game/`: the web platform where people play Werewolf and label trust
  during the game (Next.js 16, React 19, Prisma 7 on PostgreSQL, Redis, and
  Socket.IO). It includes the in-game labeling panel and the admin panel that
  exports each game. See Section 3.1 and
  [`werewolf-game/README.md`](werewolf-game/README.md).
- `llm-labeling/`: the Python engine that replays a recorded game and asks an
  LLM for trust labels. It contains the record parser, the context builder, the
  prompt sets, the inner voice, the runner, and three scripts that print the
  trust tables in the paper: `compute_alignment_trust.py` (alignment, and via
  `-d` the information and consistency dimensions), `compute_alignment_confidence.py`
  (confidence), and `count_inner_voice_usage.py` (inner-voice tool calls). See
  Section 3.2 and [`llm-labeling/README.md`](llm-labeling/README.md).
- `data-analysis/`: a Python package (managed with `uv`) that loads the human
  and LLM labels into one unified table and exposes four analysis tools
  (`compare_data`, `plot`, `delta_tool`, `correlation_tool`) to an LLM
  orchestrator the user queries in natural language. See Section 3.3, Appendix B
  (Figure 1), and [`data-analysis/README.md`](data-analysis/README.md).
- `results/`: the data. `results/game-records/` has the 31 recorded games (one
  CSV and one JSON of events plus one JSON of human labels each).
  `results/llm-labeling/` holds only the LLM label outputs behind the paper's
  tables, sorted by experiment, game, and model. These are examples, not a full
  run: they cover the games game-5NOHGS, game-UBY0T7, and game-44UT6Y (not all
  31 games), and only the model and experiment combinations reported in the
  paper. As stated in Section 4, the full sweep over all 31 games is intended but
  was not computed (see also the Limitations below).
- `design/` and `docs/`: the game rules (Section 2) and the export-format
  documentation.

The repository is at <https://git.tu-berlin.de/snet-internal/wolf-iosl-2026>.
The top-level `README` links to a `README` in each folder.

### Security/Privacy Issues and Ethical Concerns

Running the artifact is safe for the evaluator's machine. It does not turn off
any security feature and contains no exploit or malware. Two things are worth
knowing. First, the data comes from real games, but players appear only under
random color names (for example `Blue`, `Lime`); there is no file in the
repository that maps these names to real people. Second, secrets are read from a
`.env` file. The admin panel is protected by `ADMIN_SECRET`, and
`werewolf-game/docker-compose.yml` ships a default value that should be changed
before any shared deployment. The voice input is optional and only sends audio
to Deepgram when a player chooses to use it; it is not needed to reproduce
anything.

## Basic Requirements

### Hardware Requirements

1. Minimal: the game platform and the data analysis run on a normal laptop.
   Generating LLM labels needs access to an inference endpoint. This is an
   Ollama server that can serve the models used in the paper, up to
   `mistral-large:123b`, so a GPU server (or any OpenAI-compatible endpoint with
   a smaller model).
2. All runs were started from a normal desktop PC (the exact machine is listed in
   Section 5.1). The models themselves ran on the TU Berlin SNET Ollama server,
   which is only reachable from inside TU Berlin's servers.

### Software Requirements

1. OS: the stack runs on Windows, Linux, and macOS. Nothing in the
   code depends on a specific OS.
2. OS packages: `git`; Docker with Docker Compose; `uv`; and a Python 3.14
   interpreter with `pip` for the labeling engine.
3. Packaging: the game platform runs through Docker Compose with three services,
   the app (`node:20-alpine`), `postgres:16-alpine`, and `redis:7-alpine`.
4. Interpreters: the labeling engine needs Python 3.14 or newer. The analysis
   package uses Python 3.12, which `uv` installs automatically.
5. Packages: the labeling engine lists its packages in
   `llm-labeling/requirements.txt` (and `llm-labeling/pyproject.toml`); the
   analysis package pins its packages in `data-analysis/uv.lock` (pandas, SciPy,
   matplotlib, LangChain, LangGraph, pydantic); the game platform pins its Node
   packages in `werewolf-game/package-lock.json`.
6. Models: the labeling runs used `gemma4:31b`, `qwen3.6:35b`, and
   `mistral-large:123b`, with `gemma4:12b` for local checks. The analysis agent
   uses `gemma4:26b` by default (`MODEL_NAME` in `data-analysis/.env`).
7. Datasets: the games are already in `results/game-records/` (31 games). JSON
   Schemas for the file formats are in `llm-labeling/schemas/`
   (`game_events_schema.json`, `human_game_labels_schema.json`,
   `label_output_schema.json`).

### Estimated Time and Storage Consumption

- Setup: cloning and installing dependencies.
- Generating one labeling run (one game, one experiment, all 8 players): about
  20 to 90 minutes of compute, depending on the model. Mistral is the slowest;
  Gemma and Qwen finish in about 20 to 50 minutes.
- Printing a table from the committed results: a few seconds.
- Asking the analysis agent one question: a short wait, depending on the model
  and endpoint.
- The whole repository, including the committed results, is under 1 GB.

## Environment

### Set up the environment

```bash
git clone https://git.tu-berlin.de/snet-internal/wolf-iosl-2026.git
cd wolf-iosl-2026

# 1) Game platform. With Docker it runs on http://localhost:3001.
#    The admin password is ADMIN_SECRET in docker-compose.yml; change it.
cd werewolf-game
docker compose up --build

# 2) LLM Labeling Engine (Python 3.14+)
cd ../llm-labeling
python -m venv .venv && source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env        # set OLLAMA_API_KEY (and OLLAMA_API_URL)

# 3) Data Analysis Agent (uv installs Python 3.12)
cd ../data-analysis
make install                # runs: uv sync --extra dev
cp .env.example .env        # set OLLAMA_API_KEY
```

These steps follow the module READMEs
([`werewolf-game/README.md`](werewolf-game/README.md),
[`llm-labeling/README.md`](llm-labeling/README.md),
[`data-analysis/README.md`](data-analysis/README.md)), which give more detail.

To run the game platform without Docker, use `cp .env.example .env`, then
`npm install`, `npm run db:push`, and `npm run dev` (it then runs on
`http://localhost:3000`); this needs a running PostgreSQL and Redis.

### Testing the Environment

Game platform: open <http://localhost:3001>, create a room, and turn on Sandbox
Mode so bots fill the empty seats. This lets one person walk through a full game.

Analysis package: from `data-analysis/`, run the tests. They include unit tests
and integration tests against the real exports in `results/game-records/`.

```bash
uv run pytest
```

Labeling engine: run a one-phase dry run for a single player. This exercises the
full parse, context, and LLM path.

```bash
cd llm-labeling
python ./src/wolf_llm_labeling/main.py \
  ../results/game-records/game-44UT6Y-d59e923e-labels.json \
  ../results/game-records/game-44UT6Y-d59e923e.csv \
  --primary-model <model> --ollama-url <ENDPOINT> \
  --experiment a --cutoff 3 --player-name Blue --max-phases 1
```

We get one result JSON and one Markdown trace under
`results/llm-labeling/a/game-44UT6Y-.../`. This dry run follows the quickstart in
[`llm-labeling/README.md`](llm-labeling/README.md). To inspect the exact context
a model receives without calling an LLM, the same README documents
`print_context.py`; an example of that output is shown in Appendix C.1.

## Artifact Evaluation

### Main Results and Claims

#### Main Result 1: LLM trust level depends on the model

For a given game, the per-phase average alignment trust of the LLMs follows the
human pattern, but the level depends on the model. Gemma tends to trust less,
Mistral trusts almost everyone highly, and Qwen sits closest to the human values
in game-5NOHGS. Independent variables: model and phase; dependent variable:
average alignment trust. This is shown in Section 5.1, Table 2 (game-5NOHGS) and
Table 3 (game-UBY0T7). Reproduced by
[Stage 2](#stage-2-reproduce-the-paper-tables).

#### Main Result 2: Giving the model its own previous scores raises confidence

When the model also receives the player's own previous trust scores (Experiment
B, cutoff 3), its confidence is higher than with chat logs only (Experiment A,
cutoff 0). Independent variable: Experiment A versus B; dependent variable:
average confidence. Shown in Appendix D.1, Table 9 (game-5NOHGS) and Table 10
(game-UBY0T7). Reproduced by
[Stage 2](#stage-2-reproduce-the-paper-tables).

#### Main Result 3: The Human Historic Inner Voice moves labels toward human values

In Experiments D to F, where the model can ask a Human Historic Inner Voice, the
alignment trust moves closer to the human values, and the models call the voice
at different rates (Qwen calls it more often than Gemma, and most often in
Experiment D). Independent variables: experiment (D, E, F) and model; dependent
variables: average alignment trust and number of tool calls. The call counts are
in Section 5.1, Table 4; the alignment values for Experiments D to F are in
Appendix D.3, Table 12. Reproduced by
[Stage 2](#stage-2-reproduce-the-paper-tables).

### Stages

#### Stage 1: Generate LLM trust labels

- Time: about 5 minutes of work plus 20 to 90 minutes of compute per game,
  experiment, and model.
- Storage: under 100 MB.

Run the engine from `llm-labeling/`. The first positional argument is the human
labels file, the second is the events CSV. Below are Experiment A (chat only,
cutoff 0), Experiment B (chat plus own previous scores, cutoff 3), and Experiment
D (chat plus the Human Historic Inner Voice as a tool).

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

# Experiment D (inner voice as a tool, Human Historic voice, cutoff 3)
python ./src/wolf_llm_labeling/main.py \
  ../results/game-records/game-UBY0T7-140e8697-labels.json \
  ../results/game-records/game-UBY0T7-140e8697.csv \
  --primary-model gemma4:31b --ollama-url <ENDPOINT> \
  --experiment d --variant 2 --inner-voice-type human \
  --cutoff 3 --prompt-set prompts/prompt_sets/pimped.json \
  --temperature 0.5 --parallel 4
```

Each run writes one result JSON and one Markdown trace per player under
`results/llm-labeling/<experiment>/<game>/<model>/`, in the same format as the
files already in the repository. `--experiment` is required; the models are not
deterministic at temperature above 0, so the numbers vary a little between runs.
This stage supports Main Results 1 to 3.

#### Stage 2: Reproduce the paper tables

- Time: about 5 minutes of work plus under 5 minutes of compute.
- Storage: none beyond the repository.

The tables in the paper are printed by three scripts in `llm-labeling/`, which
read the committed results in `results/llm-labeling/`. Run them from the
`llm-labeling/` folder.

```bash
# Alignment-trust averages per phase, Experiments A and B
# (Section 5.1, Table 2 for game-5NOHGS and Table 3 for game-UBY0T7)
python compute_alignment_trust.py 5NOHGS -e a b
python compute_alignment_trust.py UBY0T7 -e a b

# Experiment C alignment-trust averages (Appendix D.2, Table 11)
python compute_alignment_trust.py 5NOHGS -e c

# Information and Consistency dimensions (Appendix D.5, Tables 13 and 14)
python compute_alignment_trust.py UBY0T7 -d information -e a b
python compute_alignment_trust.py UBY0T7 -d consistency -e a b

# Confidence tables (Appendix D.1, Tables 9 and 10)
python compute_alignment_confidence.py 5NOHGS -e a b
python compute_alignment_confidence.py UBY0T7 -e a b

# Inner Voice tool-call counts (Section 5.1, Table 4)
python count_inner_voice_usage.py --game UBY0T7
```

Each script prints a per-phase table to the terminal. For example,
`compute_alignment_trust.py 5NOHGS -e a b` prints the human column together with
Gemma, Qwen, and Mistral for Experiments A and B, which matches Table 2
(game-5NOHGS) in the paper. This stage supports Main Results 1 to 3.

#### Stage 3: Query the Data Analysis Agent

- Time: about 5 minutes of work plus 1 to 2 minutes of compute per question.
- Storage: none beyond the repository.

The Data Analysis Agent loads the human and LLM labels into one unified table and
answers questions by calling analysis tools. It is described
in Section 3.3, drawn as Figure 1 in Appendix B, and documented in
[`data-analysis/README.md`](data-analysis/README.md). Four tools are available:
`compare_data` (descriptive statistics for one slice, or a comparison of two
slices), `plot` (renders a slice to a PNG with a caption and the underlying
numbers), `delta_tool` (the matched-cell difference between two sources or two
trust dimensions), and `correlation_tool` (how extreme the LLM labels are versus
human, and whether confidence tracks extremity). An LLM orchestrator selects and
runs these tools and returns tool-grounded answers.

From `data-analysis/`, ask the agent a question in plain English (this is the
`make run` entry point in the README):

```bash
uv run python main.py agent --question "How does human trust in werewolves evolve across phases?"
```

We can also call a single tool directly, for example the human-versus-LLM
comparison from the README:

```bash
uv run python main.py tool compare_data --params '{
  "filters_a": {"sources": ["human"], "room_codes": ["5NOHGS"]},
  "filters_b": {"sources": ["llm"],   "room_codes": ["5NOHGS"]},
  "group_by": ["trust_type"], "correlate": true}'
```

To create a plot, call the `plot` tool. This example renders the
human-versus-LLM alignment-trust line chart for game-UBY0T7 (the plot in
Appendix C.5, Figure 2) to a PNG under `results/data-analysis/plots/`:

```bash
uv run python main.py tool plot --params '{
  "filters": {"room_codes": ["UBY0T7"], "trust_types": ["alignment"]},
  "kind": "line_per_phase"}'
```

The agent produces the same plot from a plain-English request, for example
`uv run python main.py agent --question "Plot alignment trust across phases for
game UBY0T7, comparing humans and LLMs."`

The agent answers in the terminal after a few tool calls, grounded in the tool
outputs; any plots are written to `results/data-analysis/plots/`. This stage
shows the Data Analysis Agent contribution.

## Limitations

The human games themselves cannot be reproduced from the artifact. The platform
is included so new games can be played, but the 31 games in the paper are fixed.
The exact LLM labels are also not reproducible bit for bit, because the models
run at temperature 0.5 and are hosted. The committed results, prompts, and traces
make the reported numbers checkable, and fresh runs reproduce the same trends,
usually within a few tenths of a point per phase. The committed LLM labels are
examples, not a full run: they cover mainly game-5NOHGS and game-UBY0T7 (plus
game-44UT6Y for Experiment A), not all 31 games or every model and experiment.
The full sweep was not computed because each run is slow, as noted in Section 4
and discussed in Section 6.1. Access to the SNET server is limited to
TU Berlin; anyone outside can point the engine at another Ollama or
OpenAI-compatible endpoint, which only changes the runtime and the model.

## Notes on Reusability

The game platform, the labeling engine, and the analysis package are each meant
to be reused on their own. The game platform can record
new games (Classic or Arena mode, timers, witch self-heal, sandbox bots) and
export them in the same CSV and JSON format. The labeling engine is driven by the
game records: a new experiment is one Python file under
`llm-labeling/src/experiments/`, prompts and tool text are swapped through
prompt-set JSON files and the `--prompt-set` flag, the context depth is set with
`--cutoff`, any Ollama or OpenAI-compatible model can be used through
`--primary-model` and `--ollama-url`, and a new inner voice only has to follow
the existing Python interface. The analysis package reads any files that match
the JSON Schemas, shares one set of filters across all its tools, and lets new
tools be added to the same agent.