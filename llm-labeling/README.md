# Werewolf LLM Labeling Engine

This engine runs experiments to evaluate how LLM players assess trust towards other players in the game of Werewolf.

## CLI Usage Guide

You can run the labeling engine CLI by executing the main script:

```powershell
python .\src\wolf_llm_labeling\main.py <game_record.json> <game_record.csv> [options]
```

### Positional Arguments
1. **`game_record_json`**: Path to the game record JSON labels file (e.g. `game-44UT6Y-d59e923e-labels.json`)
2. **`game_record_csv`**: Path to the game record CSV logs file (e.g. `game-44UT6Y-d59e923e.csv`)

---

### Key Options

| Option | Type | Description |
|---|---|---|
| `--primary-model` | `str` | **Required.** Model name for the main labeling agent (e.g. `gemma4:26b`). |
| `--ollama-url` | `str` | **Required.** Base URL of the Ollama server (e.g. `https://gpu.snet.tu-berlin.de/echelon/ollama`). |
| `--experiment` | `str` | **Required.** The experiment file/id to run: `a`, `b`, `c`, `d`, `e`, or `f` |
| `--inner-voice-model` | `str` | Optional. Model name to use for the inner trust voice (defaults to the primary model) |
| `--player-name` | `str` | Optional. Specific player name or index (e.g. `Blue` or `0`) to run labeling for. Runs for **all players** if omitted |
| `--max-phases` | `int` | Optional. Maximum number of phases to evaluate (default: 0 for all phases) |
| `--experiment-args` | `str` | Optional. Arguments passed to the experiment. For A-C, it is `<cutoff>`. For D-F, it is `<cutoff> <variant>` (e.g. `"3 2"`) |
| `--formatter` | `str` | Optional. Context format type: `markdown` (default) or `json` |
| `--context-as-tool` | `flag` | Optional. If set, the game context is retrieved dynamically by the LLM via tool call instead of pre-injected in the prompt |
| `--prompt-set` | `str` | Optional. Path to a JSON file mapping custom prompts |
| `--output-dir` | `str` | Optional. Base directory where JSON results are saved (default: `./results/llm-labeling`) |

---

## Example Execution Commands

### 1. Run Experiment A (No Inner Voice, Cutoff 3 phases back)
```powershell
python .\src\wolf_llm_labeling\main.py `
  "..\results\game-records\game-44UT6Y-d59e923e-labels.json" `
  "..\results\game-records\game-44UT6Y-d59e923e.csv" `
  --primary-model "gemma4:26b" `
  --ollama-url "https://gpu.snet.tu-berlin.de/echelon/ollama" `
  --experiment "a" `
  --experiment-args "3" `
  --player-name "Blue"
```

### 2. Run Experiment D (Variant 2: Agentic Tool Loop, Cutoff 3, JSON Formatter)
```powershell
python .\src\wolf_llm_labeling\main.py `
  "..\results\game-records\game-44UT6Y-d59e923e-labels.json" `
  "..\results\game-records\game-44UT6Y-d59e923e.csv" `
  --primary-model "gemma4:26b" `
  --ollama-url "https://gpu.snet.tu-berlin.de/echelon/ollama" `
  --experiment "d" `
  --experiment-args "3 2" `
  --formatter "json" `
  --player-name "Blue"
```

---

## Output Location & Schema

Results are written automatically to:
*   `results/<experiment>/<game_id>/<player_name>-<uuid>.json` (Structured JSON results)
*   `results/<experiment>/<game_id>/<player_name>-<uuid>-thinking.md` (Readable markdown companion file containing the complete thinking traces / chains of thought of the LLM for each phase and step)

Example Schema:
```json
{
  "game_id": "d59e923e-8478-4514-9ccd-8d4ac5a18d5a",
  "game_file": "game-44UT6Y-d59e923e",
  "player_name": "Blue",
  "trust_scale_mode": "likert",
  "models": {
    "primary_model": "gemma4:26b"
  },
  "prompts": {},
  "time": "2026-06-28T20:30:00Z",
  "experiment": "d",
  "formatter": "json",
  "experiment_args": "3 2",
  "temperature": 1.0,
  "max_phases": 3,
  "context_as_tool": false,
  "total_phases": 9,
  "alive_phases": 6,
  "phases": [
    {
      "phase_idx": 0,
      "context": "{ ... }",
      "inner_voice": [
        {
          "request": { "player_name": "Orange" },
          "response": "{ \"alignment\": { \"trust\": 7, \"confidence\": 3 } }"
        }
      ],
      "labels": {
        "Orange": {
          "alignment": {
            "trust": 7,
            "trust_likert": "VERY_HIGH_TRUST",
            "confidence": 3,
            "confidence_likert": "HIGH_CONFIDENCE"
          },
          "information": null,
          "consistency": null,
          "reasoning": "Orange has been supportive of the village goals."
        }
      },
      "reasoning": "Evaluating Orange based on the inner trust voice...",
      "thinking_process": [
        "First, I need to check my role... Gold is a wolf. Orange was elected Mayor...",
        "Now I should report the labels..."
      ]
    }
  ]
}
```

---

## Local Testing with LM Studio

LM Studio hosts local models behind an OpenAI-compatible API endpoint (default: `http://localhost:1234/v1`). 

If the `--ollama-url` parameter contains `1234` or `/v1`, the labeling engine automatically switches to the `ChatOpenAI` client behind the scenes. This allows you to run trust evaluations locally against any loaded model (e.g. Gemma, Llama, etc.)

Example local command:
```powershell
python .\src\wolf_llm_labeling\main.py `
  "..\results\game-records\game-44UT6Y-d59e923e-labels.json" `
  "..\results\game-records\game-44UT6Y-d59e923e.csv" `
  --primary-model "your-local-model-name" `
  --ollama-url "http://localhost:1234/v1" `
  --experiment "a" `
  --experiment-args "3" `
  --player-name "Blue" `
  --max-phases 1
```

### CLI Parameters

| Parameter | Type | Description |
| :--- | :--- | :--- |
| `game_record_json` | Positional | Path to the game record JSON file. |
| `game_record_csv` | Positional | Path to the game record CSV file. |
| `--primary-model` | String | Model ID for the primary labeling agent. |
| `--inner-voice-model` | String | Model ID for the inner voice agent (defaults to primary model). |
| `--ollama-url` | String | URL of the Ollama server (or `http://localhost:1234/v1` for LM Studio). |
| `--player-name` | String | Player name or index to label (runs for all players if omitted). |
| `--output-dir` | String | Base output directory (default: `./results/llm-labeling`). |
| `--experiment` | String | Experiment ID module to load (e.g. `a`, `b`, etc.). |
| `--experiment-args` | String | Configuration arguments passed to the experiment (e.g. `"3 2"`). |
| `--max-phases` | Integer | Maximum number of phases to label (default: `0` for all alive phases). |
| `--prompt-set` | String | Path to prompt-set JSON configuration file. |
| `--prompt-dir` | String | Directory containing the prompts (default: `./prompts`). |
| `--formatter` | String | Context format type: `markdown` or `json`. |
| `--context-as-tool` | Flag | If set, retrieves the game context via tool call instead of pre-injecting it. |
| `--temperature` | Float | Generation temperature for LLM calls (default: `0.0`, recommended: `0.2` for Gemma). |
| `--use-likert` | Flag | If set, LLM evaluates trust via a 7-point Likert scale (translated to numbers in JSON). |
| `--runs` | Integer | Number of independent repeated runs to execute (default: `1`). Useful for gathering averages. |
| `--chronology` | String | Chronology formatting type: `numeric` (default) or `timestamp` (for time prefixes). |

---

## Batch Execution & Automation

There are two ways to automate runs across multiple games, models and experiments:

### 1. Fully Automated Python Script (`run_all.py`)

The `run_all.py` script automatically scans for all healthy game records inside `./results/game-records/` and executes experiments A through F for the specified models by calling the labeling engine directly:

```powershell
python .\run_all.py
```

You can edit `run_all.py` directly to adjust the list of active models, the Ollama server URL, or the experiments you wish to run.

### 2. Config-Driven Batch Runner (`batch_runner.py`)

Alternatively, you can run custom configurations defined in a JSON file (args are for phases or inner trust):

1. Create a `batch_config.json` file:
```json
{
  "ollama_url": "https://gpu.snet.tu-berlin.de/echelon/ollama",
  "primary_model": "gemma4:26b",
  "runs_count": 10,
  "runs": [
    { "experiment": "a", "args": "3" },
    { "experiment": "d", "args": "3 2", "runs_count": 5 }
  ]
}
```
*(Note: You can specify `"runs_count"` (or `"repeat"`) globally, or override it individually inside a specific run dictionary. Defaults to 1).*

2. Execute the batch:
```powershell
python .\src\wolf_llm_labeling\batch_runner.py --config batch_config.json
```

To run default presets across all game files with repeated executions without a configuration file:
```powershell
python .\src\wolf_llm_labeling\batch_runner.py --primary-model "gemma4:26b" --runs 100
```

---

## Context Structure & Information Filtering

To prevent **information leakage**, the context builder dynamically filters all phase logs based on the role of the player being evaluated:
*   **Werewolves**: Can see Werewolf chat, Werewolf night votes, and public events/chats. Cannot see Seer investigations or Witch actions
*   **Seer**: Can see Seer investigations (`SeerRevealed`) and public events/chats. Cannot see Werewolf chat, night votes, or Witch actions.
*   **Witch**: Can see Witch actions (`WitchKilled`, `WitchSaved`) and public events/chats.
*   **Villagers**: Can only see public events (deaths, exiles, village chat).
*   **Mayor Election Votes**: Individual votes for the Mayor are anonymous and hidden from all players. Only the final result is visible.

All phase logs are grouped chronologically under the `[Moderator]` header (representing system events).

### 1. Markdown Context Example (Default)
Below is an example of the context generated for a **Werewolf** player (`Blue`) at Phase 0 (Morning):

```markdown
# Game Information

## Static Data

Your name is: Blue
Your role is: Werewolf

## Current Game State

- Day: 1
- Last Phase: None
- Current Phase: Morning
- Players Alive (7): Blue, Brown, Gold, Gray, Lime, Orange, Red
- Next Phase: Day
- Dead Players:
  - Purple (Villager): killed

# Current Phase

- Day: 1
- Phase: Morning
- This is the current phase.
- Players alive at end of phase: 7
- Players no longer alive at end of phase:
  - Purple (Dead)

## Phase chronology
1. [Moderator] Night 1 begins.
2. Conversation among players with role Werewolf:
   2.1 [Blue] who do you think we should kill?
   2.2 [Gold] no idea
   2.3 [Gold] random?
   2.4 [Blue] ok I picked purple
   2.5 [Gold] ok
3. Players with role Werewolf vote whom to kill:
   3.1 Blue voted for Purple (Kill)
   3.2 Gold voted for Purple (Kill)
4. Purple was found dead.
5. [Moderator] The village must elect a Mayor.
6. Conversation among all players:
   6.1 [Orange] I can do it
   6.2 [Lime] motivated ain ya
   6.3 [Blue] hahaha
   6.4 [Gold] everyone can but why you?
   6.5 [Orange] born to lead
   6.6 [Gold] ahhahhah Lime
   6.7 [Blue] nice one
   6.8 [Orange] I will always maximize shareholder value
   6.9 [Orange] promise
7. [Only visible to you] Blue did not vote in the mayor election.
8. Blue was elected Mayor.
```

### 2. JSON Context Example (`--formatter json`)
If `--formatter json` is passed, the same context is formatted as a recursive JSON tree structure:

```json
{
  "subsections": [
    {
      "header": "Game Information",
      "subsections": [
        {
          "header": "Static Data",
          "content": "- Your name is: Blue\n- Your role is: Werewolf"
        },
        {
          "header": "Current Game State",
          "content": "- Current Day: 1\n- Last Phase: None\n- Current Phase: Morning\n- Players Alive (7): Blue, Brown, Gold, Gray, Lime, Orange, Red\n- Next Phase: Day\n- Dead Players:\n  - Purple (Villager): killed"
        }
      ]
    },
    {
      "header": "Current Phase",
      "content": "- Day: 1\n- Phase: Morning\n- This is the current phase.\n- Players alive at end of phase: 7\n- Players no longer alive at end of phase:\n  - Purple (Dead)\n\n## Phase chronology\n1. [Moderator] Night 1 begins.\n2. Conversation among players with role Werewolf:\n   2.1 [Blue] who do you think we should kill?\n   2.2 [Gold] no idea\n   2.3 [Gold] random?\n   2.4 [Blue] ok I picked purple\n   2.5 [Gold] ok\n3. Players with role Werewolf vote whom to kill:\n   3.1 Blue voted for Purple (Kill)\n   3.2 Gold voted for Purple (Kill)\n4. Purple was found dead.\n5. [Moderator] The village must elect a Mayor.\n6. Conversation among all players:\n   6.1 [Orange] I can do it\n   6.2 [Lime] motivated ain ya\n   6.3 [Blue] hahaha\n   6.4 [Gold] everyone can but why you?\n   6.5 [Orange] born to lead\n   6.6 [Gold] ahhahhah Lime\n   6.7 [Blue] nice one\n   6.8 [Orange] I will always maximize shareholder value\n   6.9 [Orange] promise\n7. [Only visible to you] Blue did not vote in the mayor election.\n8. Blue was elected Mayor."
    }
  ]
}
```

### 3. Local Context Inspection Tool
A utility script `print_context.py` is included in the project root to inspect the filtered context generated for any game phase/player:

```powershell
# Print the Markdown context of Day 1 Morning for "Blue":
python print_context.py --player "Blue" --phase 0

# Print the JSON context of Day 1 Morning for "Blue":
python print_context.py --player "Blue" --phase 0 --json
```
