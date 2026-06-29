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
`results/<experiment>/<game_id>/<player_name>-<uuid>.json`

Example Schema:
```json
{
  "game_id": "game-44UT6Y-d59e923e",
  "player_name": "Blue",
  "models": {
    "primary_model": "gemma4:26b"
  },
  "prompts": {},
  "time": "2026-06-28T20:30:00Z",
  "experiment": "d",
  "formatter": "json",
  "experiment_args": "3 2",
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
          "alignment": { "trust": 7, "confidence": 3 },
          "strategic": null,
          "consistency": null,
          "reasoning": "Orange has been supportive of the village goals."
        }
      },
      "reasoning": "Evaluating Orange based on the inner trust voice..."
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
  "runs": [
    { "experiment": "a", "args": "3" },
    { "experiment": "d", "args": "3 2" }
  ]
}
```

2. Execute the batch:
```powershell
python .\src\wolf_llm_labeling\batch_runner.py --config batch_config.json
```

To run default presets across all game files without a configuration file:
```powershell
python .\src\wolf_llm_labeling\batch_runner.py --primary-model "gemma4:26b"
```
