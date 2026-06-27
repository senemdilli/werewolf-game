# CLI

## Positional arguments
`app <game_record.json> <game_record.csv>`

## Options
- `--primary-model` the model to run for labeling agent e.g. `gpt-oss:20b`
    - Error, if the model is not supported by the server
    - required
- `--inner-voice-model` the model to use for the inner voice (if one uses it)
    - optional
    - default: same as primary model
    - Error, if the model is not supported by the server
- `--ollama-url` url of the ollama instance
    - required
- `--player-name` runs the labeling with a given player name, or an index of the player. e.g. `--player-name Green`/`--player-name 0`
    - Error, for invalid names, ids
    - If not provided, run the labeling for all players
- `--output-dir` base output directory
    - defaults to `./results/llm-labeling`
- `--experiment` experiment id e.g. `a.py` or `b.py`
    - ideally loaded dynamically from experiments folder
    - required
- `--max-phases` limits the maximum number of phases to label
    - optional
    - default: 0 (infinite)
    - should not change total_phases/alive_phases in the results
- `--experiment-args` a string, that is passed to the current argument to configure it. e.g. to configure the phase cutoff\
    - optional
- `--prompt-set` a path to a json file, containing a dictionary of str -> str, where the keys are prompt ids and the values are relative paths to prompt files (text files)
    - optional
- `--prompt-dir` defines in which dir all prompts are
    - optional
    - default: `./prompts`
- `--formatter`
    - optional
    - default: `markdown`

## Keys
Provided via env var

## Output (files)
Let `res://` be the output dir. The output will be stored inside `res://<experiment>/<game-id>/<player-name>-<random-uuid>.json`. Where `experiment` is the file name of the experiment (without the extension) e.g. `a` for `a.py`. `game-id` is the same as when loading in the `game_record.json`.

Note: we cant just use the player name, since we can have multiple runs with the same experiment & game (different args/models)

## Output (json)
each json files contains the labels of a given players perspective.

```json
{
    "player_name": "Joe",
    "models": {
        "primary_model": "gpt20",
        "inner_voice_model": "<only exists, if different to primary model>"
    },
    "prompts": <dump of the raw prompt-set cli input>,
    "time": "<timestamp of labeling>",
    "experiment": "a",
    "formatter": "markdown",
    "experiment_args": "<raw input string>",
    "total_phases": <number of phases in the game>,
    "alive_phases": <number of phases the player is alive>,
    "phases": [
        {
            "phase_idx": 3,
            "context": "<context provided to the llm>",
            "inner_voice": [
                {
                    "request": <agent tool request>,
                    "response": <agent tool response>
                },
                ...
            ],
            "labels": {
                "<labeled-player-name>": {
                    "alignment": {
                        "trust": 1,
                        "confidence": 1
                    },
                    "strategic": ...,
                    "consistency": ...,
                    "reasoning": "<text>"
                },
                ...
            },
            "reasoning": <dump of the full reasoning chain of the llm, if available>
        }
    ]
}
```

(Context and) inner voice can be non deterministic, so we need to save them.

TODO: create a schema for the json (but which type?)

TODO: should these logs also contain game data (for easier analytics), or just the labeling data?

## Output (stdout)
Print the progress of the labeling (i.e. x/y phases completed. in that phase z/w players completed)

At the end print all files that have been written to.

## Experiments
We need to unify the experiment interface. Since experiments take different parameters, we allow them to just pass a raw string as an argument from the command line. e.g. for cutoff
Use simple shell style, space separated inputs, for the args. e.g. for cutoff the input would just be "6" for 6 phases. When needing 2 args it would be "<arg1> <arg2>"

```
class LLMModelProviders:
    primary
    inner_voice
```


```
def experiment(
    player_name: PlayerName,
    args: str,
    models: LLMModelProviders
) -> tuple[ContextProvider, InnerVoice | None]:
```

Models are already set up models that are ready to use

## Prompts
We need to allow to switch prompts to see how that changes the outputs.

```python
class PromptSet:    
    def get_prompt(prompt_id: str, args: dict[str, str], default_prompt: str | None = None): 
        """
            Returns a filled out prompt using string.Template for templating.
            If the prompt does not exist in the internal prompt storage use the default prompt as a fallback.
            If that also doesn't exist, an error is thrown.
            Fills out the prompt with args
        """
        ...


    def load(path: str):
        "the path points to a json file, which contains a dict of prompt_id -> path/to/prompt entries. loads these prompts"
        ...

    def __str__(self):
        """Prints all prompt templates"""
        ...

```

We use PromptSet as an argument for constructing a context or a response from an inner voice. This way we can inject
custom prompts when wanted.

```python

class InnerVoice(Protocol):
    def ask(self, player_name: PlayerName, context: Ctx | None, game_records: GameRecord, prompt_set: PromptSet, phase_idx: int) -> TrustScores:
        ...

    def tool_description(self, prompt_set: PromptSet) -> str:
        ...


class ContextProvider(Protocol):
    def get_context(self, game_record: GameRecord, prompt_set: PromptSet, phase_idx: int) -> "Ctx | None": ...

    def get_topness(self) -> float: ...

```

Eg
```python
 def tool_description(self, prompt_set: PromptSet) -> str:
        return prompt_set.get_prompt('inner_voice__random_voice', {},
            "Returns a random trust assessment for the given player. This is a "
            "baseline control and is not grounded in any game evidence."
        )
```


Label once now accepts a prompt set


Prompt set stores internally just a dict of prompt_id to prompts

ALL prompts should be accessed though get_prompt. including system prompts, tool call explanations, contexts, etc.
so we can swap them out dynamically

when giving id's to prompts use this convention: `category__subcategory`, e.g. `inner_voice__random_inner_voice`. Use snake case class names for class prompts.
All prompts should have some default.

## Formatting
We need a way to change the output format for llms, to see how that changes their behavior (json vs markdown)

```python
FormatterType = Literal["markdown", "json"]
```

Ctx.to_string now takes a FormatterType, and depending on it, it will return differently formatted outputs.

Define a helper method formatted_trust_scores in labeling.py that respectively takes in a trust score, a formatter type and returns a formatted score.
It's called in label_once.

label_once now also takes the formatter type as an argument.



## New label_once
With all these changes the new interface is:
```python
def label_once(
    models: LLMModelProviders,
    prompt_set: PromptSet,
    context: ContextProvider,
    inner_voice: InnerVoice | None,
    formatter_type: FormatterType
    game_data: GameRecord,
    phase_idx: int,
) -> tuple[dict[PlayerName, Label], LLMCallInfo]:
```