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
