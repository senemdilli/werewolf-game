# Werewolf LLM Labeling Engine

This engine runs experiments to evaluate how LLM players assess trust towards other players in the game of Werewolf.

## Setup

Before running the engine, create a `.env` file in the `llm-labeling/` directory and configure your Ollama API key:

```env
OLLAMA_API_KEY=your_key_here
```

## CLI Usage Guide

> **Important**:
> Make sure your terminal working directory is inside the `llm-labeling/` subfolder (`cd llm-labeling`) before executing any commands!

Execute the main labeling script:

```powershell
cd llm-labeling

python .\src\wolf_llm_labeling\main.py <game_record.json> <game_record.csv> [options]
```

### Positional Arguments
1. **`game_record_json`**: Path to the game record JSON labels file (e.g. `game-44UT6Y-d59e923e-labels.json`)
2. **`game_record_csv`**: Path to the game record CSV logs file (e.g. `game-44UT6Y-d59e923e.csv`)

---

### Key Options

| Option | Type | Description |
|---|---|---|
| `--primary-model` | `str` | **Required.** Model name for the main labeling agent. Use `"any"` or `"default"` to auto-detect the first available model on the server |
| `--ollama-url` | `str` | **Required.** Base URL of the Ollama server (e.g. `https://gpu.snet.tu-berlin.de/echelon/ollama`) |
| `--experiment` | `str` | **Required.** The experiment file/id to run: `a`, `b`, `c`, `d`, `e`, or `f` |
| `--inner-voice-model` | `str` | Optional. Model name to use for the inner trust voice (defaults to the primary model) |
| `--player-name` | `str` | Optional. Specific player name or index (e.g. `Blue` or `0`) to run labeling for. Runs for **all players** if omitted |
| `--max-phases` | `int` | Optional. Maximum number of phases to evaluate (default: 0 for all phases) |
| `--cutoff` | `int` | Optional. Number of historical phases to look back for context (used in experiments A-F) |
| `--variant` | `int` | Optional. Inner trust voice variant for experiments D-F (`1` for pre-injected context, `2` for agentic tool loop, default: `2`) |
| `--inner-voice-type` | `str` | Optional. Inner trust voice type for experiments D-F (`llm` (default), `human`, `random`, or `constant`) |
| `--experiment-args` | `str` | Legacy (now splitted). Optional. Space-separated string argument containing `<cutoff> [variant] [inner_voice_type]` (e.g. `"3 2 human"`) |
| `--formatter` | `str` | Optional. Context format type: `markdown` (default) or `json` |
| `--context-as-tool` | `flag` | Optional. If set, the game context is retrieved dynamically by the LLM via tool call instead of pre-injected in the prompt |
| `--prompt-set` | `str` | Optional. Path to a JSON file mapping custom prompts |
| `--prompt-dir` | `str` | Optional. Directory containing the prompts (default: `./prompts`) |
| `--output-dir` | `str` | Optional. Base directory where JSON results are saved (default: `../results/llm-labeling`) |
| `--use-numeric` | `flag` | Optional. If set, forces numeric integer scale (1-100) instead of the default Likert scale |
| `--likert-type` | `str` | Optional. Likert scale format to use: `agree-disagree` (strongly disagree to strongly agree, default) or `legacy` (very low to very high trust) |
| `--parallel` | `int` | Optional. If set, runs the labeling tasks for different players concurrently (specify number of threads, e.g. `--parallel 4`. Default: `2` if flag is present but value omitted). |
| `--temperature` | `float` | Optional. LLM generation temperature (default: `0.0`) |
| `--runs` | `int` | Optional. Number of independent repeated runs to execute (default: `1`). Useful for gathering averages |
| `--chronology` | `str` | Optional. Chronology formatting type: `numeric` (step numbers, default) or `timestamp` (for time prefixes) |


---

## Example Execution Commands

### 1. Run Experiment A (No Inner Voice, Cutoff default 0 phases back, Temperatur 0.5, 4 Threads)
```powershell
python .\src\wolf_llm_labeling\main.py `
  "..\results\game-records\game-5NOHGS-b57eee98-labels.json" `
  "..\results\game-records\game-5NOHGS-b57eee98.csv" `
  --primary-model "qwen3.6:35b" `
  --ollama-url "https://gpu.snet.tu-berlin.de/echelon/ollama" `
  --experiment "a" `
  --prompt-set "prompts/prompt_sets/pimped.json" `
  --temperature 0.5 `
  --parallel 4
```

### 2. Run Experiment D (Variant 2: Agentic Tool Loop, Cutoff 3, 4 Threads)
```powershell
python .\src\wolf_llm_labeling\main.py `
  "..\results\game-records\game-5NOHGS-b57eee98-labels.json" `
  "..\results\game-records\game-5NOHGS-b57eee98.csv" `
  --primary-model "gemma4:31b" `
  --ollama-url "https://gpu.snet.tu-berlin.de/echelon/ollama" `
  --experiment "d" `
  --cutoff 3 `
  --variant 2 `
  --inner-voice-type "human" `
  --prompt-set "prompts/prompt_sets/pimped.json" `
  --temperature 0.5 `
  --parallel 4
```

---

## Output Location & Schema

Results are written automatically to:
*   `results/<experiment>/<game_id>/<sanitized_model_name>/<player_name>-<timestamp>-<uuid>.json` (Structured JSON results)
*   `results/<experiment>/<game_id>/<sanitized_model_name>/<player_name>-<timestamp>-<uuid>-trace.md` (Markdown trace file containing the run configuration, chronologically reconstructed thinking events, tool calls, tool results and fallbacks)

Note: Results are saved in the Git root directory

Example (shortened):
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
  "cutoff": 3,
  "variant": 2,
  "inner_voice_type": "human",
  "formatter": "json",
  "temperature": 0.5,
  "max_phases": 3,
  "context_as_tool": false,
  "total_phases": 9,
  "alive_phases": 6,
  "phases": [
    {
      "phase_idx": 0,
      "context": "{...}",
      "inner_voice": [
        {
          "request": { "player_name": "Orange" },
          "response": "Advice for Orange:\nAlignment Trust: STRONGLY_AGREE (Confidence: HIGH_CONFIDENCE)\nInformation Trust: NEUTRAL (Confidence: MEDIUM_CONFIDENCE)\nConsistency Trust: AGREE (Confidence: HIGH_CONFIDENCE)"
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
          "information": {
            "trust": 6,
            "trust_likert": "AGREE",
            "confidence": 2,
            "confidence_likert": "MEDIUM_CONFIDENCE"
          },
          "consistency": {
            "trust": 4,
            "trust_likert": "NEUTRAL",
            "confidence": 1,
            "confidence_likert": "LOW_CONFIDENCE"
          },
          "reasoning": "Orange has been supportive of the village goals."
        }
      },
      "reasoning": "Evaluating Orange based on the inner trust voice...",
      "thinking_process": [
        "First, I need to check my role... Orange was elected Mayor..."
      ]
    }
  ]
}
```

---


## System Prompt Files & Prompt Sets

The engine supports multiple configuration "Prompt Sets" (JSON mapping files). You can choose which set of prompt text files to load using the `--prompt-set` parameter:

#### 1. Default Prompt Set (`prompts/prompt_sets/simple.json` - Default)
Depending on the chosen CLI scale and type, it loads:
- **`agree-disagree` Likert scale** (Default): Loads [self_aware_and_simple_rules.txt](file:///prompts/system_prompts/self_aware_and_simple_rules.txt)
- **`legacy` Likert scale** (via `--likert-type legacy`): Loads [self_aware_and_simple_rules_legacy.txt](file:///prompts/system_prompts/self_aware_and_simple_rules_legacy.txt)
- **Numeric scale** (via `--use-numeric`): Loads [self_aware_and_simple_rules_numeric.txt](file:///prompts/system_prompts/self_aware_and_simple_rules_numeric.txt)

#### 2. Pimped Prompt Set (`prompts/prompt_sets/pimped.json`)
Enables Sandro's revised instructions designed to guide LLM behavior:
- **`agree-disagree` Likert scale** (Default): Loads [pimped_system_prompt.md](file:///prompts/system_prompts/pimped_system_prompt.md)
- **Numeric scale** (via `--use-numeric`): Loads [pimped_system_prompt_numeric.md](file:///prompts/system_prompts/pimped_system_prompt_numeric.md)

#### Context Injection Placeholder
If a system prompt file contains the substring `[PLACEHOLDER FOR GAME CONTEXT]`, the labeling engine will automatically replace it with the formatted game state and conversation history at runtime. Otherwise, the context is appended to the user instruction message.

#### 3. Configurable Tool Instructions & Descriptions for Inner Voice
In **Variant 2 (explanation see below)**, you can configure both the prompt instruction that introduces the `ask_inner_trust_voice` tool (for real Agentic Loop) and the natural language descriptions presented for each inner voice provider

To do this, add the corresponding keys to your prompt set JSON file (pointing to text files relative to your prompt directory):

```json
{
  "system_prompt": "system_prompts/pimped_system_prompt.md",
  "inner_voice__random_voice": "inner_voices/tool_descriptions/random_voice.txt",
  "inner_voice__human_historic_voice": "inner_voices/tool_descriptions/historic_voice.txt",
  "inner_voice__llm_voice": "inner_voices/tool_descriptions/llm_voice.txt",
  "inner_voice__constant_voice": "inner_voices/tool_descriptions/constant_voice.txt",
  "inner_voice_tool_instruction": "inner_voices/tool_instructions/default_instruction.txt"
}
```

*   **Replacing a Placeholder:** If your system prompt contains `[PLACEHOLDER FOR INNER VOICE TOOL]`, the engine replaces it with the loaded instruction text
*   **Appended by Default:** If the placeholder is missing, the instruction is automatically appended to the end of the system prompt
*   **Fallback Defaults:** If any description key is omitted from the prompt set JSON, the engine automatically uses its built-in fallback text for that voice type

## Inner Voice Execution Variants (Variant 1 vs. Variant 2)

Experiments D, E, and F support all 4 inner voice providers (`human`, `llm`, `random`, `constant`) in two distinct execution modes:
*   **Variant 1 (Pre-Injected Context/Passive):** The inner trust advice (e.g., historic human ratings, LLM gut feelings, random, or constant scores) is pre-calculated for all active players and injected directly into the initial prompt context text. The model receives the advice passively without executing any tool calls
*   **Variant 2 (Agentic Tool Loop/Active):** The inner trust advice is NOT pre-injected. Instead, the model is exposed to the `ask_inner_trust_voice` tool and autonomously decides whether, when, and for which specific player(s) it wants to query advice during its decision-making loop

---

## Multi-Model & Inner Voice Architecture

The labeling engine supports multiple inner voice providers to analyze decision-making dynamics:
1. **Primary Model (`--primary-model`)**: The main "deciding" agent that receives the game context, makes arguments, and reports the final trust labels
2. **Inner Voice Model (`--inner-voice-model`)**: The independent "gut-feeling" voice called inside Variant 2 tool loops

```text
Main Labeling Agent / Decider (primary_model)
└── [Exposed Tool] ask_inner_trust_voice
    └── [Calls] Inner Voice Provider
        ├── Option 1: llm        ──> Independent Inner Voice Model (inner_voice_model) / Self-Ask
        ├── Option 2: human      ──> Historic Human Ratings (Human Labels JSON Loader)
        ├── Option 3: random     ──> Random Control Baseline
        └── Option 4: constant   ──> Configured Constant Scores Baseline
```

This architecture allows studying whether a primary agent (e.g., `gemma4:31b`) "listens" to a different inner voice model (e.g., `qwen3.6:35b`), human player history, or control baselines when making trust evaluations.


---

## Context Structure & Information Filtering

To prevent information leakage, the context builder dynamically filters all phase logs based on the role of the player being evaluated (because Game Results have every event):
*   **Werewolves**: Can see Werewolf chat, Werewolf night votes, and public events/chats. Cannot see Seer investigations or Witch actions
*   **Seer**: Can see Seer investigations (`SeerRevealed`) and public events/chats. Cannot see Werewolf chat, night votes, or Witch actions
*   **Witch**: Can see Witch actions (`WitchKilled`, `WitchSaved`) and public events/chats
*   **Villagers**: Can only see public events (deaths, exiles, village chat)
*   **Mayor Election Votes**: Individual votes for the Mayor are anonymous and hidden from all players. Only the final result is visible

All phase logs are grouped chronologically under the `[Moderator]` header (representing system events)

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
# Print the Markdown context of Day 1 Morning for Blue:
python print_context.py --player "Blue" --phase 0

# Print the JSON context of Day 1 Morning for Blue:
python print_context.py --player "Blue" --phase 0 --json
```


---

## Local Testing with LM Studio

LM Studio hosts local models behind an OpenAI-compatible API endpoint (default: `http://localhost:1234/v1`) 

If the `--ollama-url` parameter contains `1234` or `/v1`, the labeling engine automatically switches to the `ChatOpenAI` client behind the scenes. This allows to run trust evaluations locally against any loaded model (e.g. Gemma, Llama, etc.)

Example local command:
```powershell
python .\src\wolf_llm_labeling\main.py `
  "..\results\game-records\game-44UT6Y-d59e923e-labels.json" `
  "..\results\game-records\game-44UT6Y-d59e923e.csv" `
  --primary-model "your-local-model-name" `
  --ollama-url "http://localhost:1234/v1" `
  --experiment "a" `
  --cutoff 3 `
  --player-name "Blue" `
  --max-phases 1
```

---
## Batch Execution & Automation

> NOTE:
> By default (without specifying a specific game ID via `game_pattern`), `batch_runner.py` executes all available game files in the game-records directory and repeat runs sequentially to avoid server overloading. Consequently, large batch runs take a significant amount of time to complete and are less extensively tested than direct single-run commands

You can automate experiments across multiple games, models and repetitions using the config-driven **Batch Runner (`batch_runner.py`)**:

### 1. Config-Driven Execution

Create a `batch_config.json` file:
```json
{
  "ollama_url": "https://gpu.snet.tu-berlin.de/echelon/ollama",
  "primary_model": "gemma4:31b",
  "prompt_set": "prompts/prompt_sets/pimped.json",
  "temperature": 0.5,
  "parallel": 4,
  "runs_count": 10,
  "runs": [
    { "experiment": "a", "cutoff": 3 },
    { "experiment": "d", "cutoff": 3, "variant": 2, "inner_voice_type": "human", "game_pattern": "game-44UT6Y*.csv", "runs_count": 5 }
  ]
}
```
*(Note: Parameters like `game_pattern` (e.g. `"game-44UT6Y*.csv"` for specific games), `prompt_set`, `temperature`, `parallel`, `chronology` or `runs_count` can be specified globally or overridden per run).*

Execute the batch runner with your config file:
```powershell
python .\src\wolf_llm_labeling\batch_runner.py --config batch_config.json
```

### 2. Direct CLI Preset Execution

To run default presets across all game files with repeated executions without a configuration file (here ALL games):
```powershell
python .\src\wolf_llm_labeling\batch_runner.py --primary-model "gemma4:31b" --runs 10
```


