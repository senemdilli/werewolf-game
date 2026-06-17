language: python (3.14), package manager: pip, libraries: langchain


The core component of the system is the `label_once` function, which takes in some context and an inner voice and from that it manages the llm to compute their trust scores.

# Architecture

# Game Records
Recorded games (csv and json) loaded into pyhton objects. the game records are organized into phases (each phase in the normal game ends with labeling). The format is:

```
struct Score:
	trust: 1-7
	confidence: 1-3

struct TrustScores:
	alignmet
	strategic
	consistency

struct Label:
	trust_scores: TrustScores
	reasoning: str

struct Message:
	forum: VillageChat|WerewolfChat
	player_name
	message

struct Vote:
	reason: Kill|Exile|Mayor
	player_name
	voted_for

union Event:
	class KillEvent:
		affected_player : PlayerName | None // Could have been skipped
	class ExileEvent:
		affected_player  : PlayerName | None
	class MayorElected:
		affected_player  : PlayerName | None
	class SeerRevealed:
		affected_player  : PlayerName
	class WitchKilled:
		affected_player  : PlayerName
	class WitchSaved:
		affected_player  : PlayerName
	
	
	
enum PhaseType:
	Day // daytime discussion
	Evening // exile voting
	Morning // before discussion

enum Role:
	Werewolf
	Villager
	Seer
	Witch

enum PlayerStatus:
	Mayor
	Alive
	Dead
	Exiled

class GameRecord:
	fn read_from_files(paths) -> None
	
	get_players() -> dict[PlayerName, Role]
	
	get_phase_type(phase_idx) -> PhaseType
	
	// everything that happend during that phase in chronological order
	get_phase_data(phase_idx) -> list[Message | Vote | Event]
	
	get_player_status(phase_idx, player_name) -> PlayerStatus
	
	// Returns the labels  a player has made when phase_idx has ended
	get_labels(phase_idx) -> dict[PlayerName, list[Label]]
		
```

Note: I think we can ignore the exact timestamps for events at the moment, since the most relevant thing is the ordering, not the exact timings.
## Context
The stuff the llm will actually see. It is build based on the game records.

```
// A simple header, subheader, ... representation of the required context
// This is basically an unformatted string
class Ctx:
	header: str | None // leaving the header empty omits it
	content: str | None
	subsections: list[Ctx]
	
	// Returns a markdown like formatting of the object (example below)
	def to_string() -> str


// The 'factory' that create a Ctx object to use
interface Context:
	// Generate a concrete context, depending on the type of context we want
	// We need to do that on the fly depending on the acutal game data we receive inside of `label_once`
	// It is allowed to return no context (e.g. if there is no historical data just jet for the game, as it just started)
	fn get_context(game_records, phase_idx) -> Ctx | null
	
	// when joining contexts, handles in which order contexts should be joined.
	// the hightest topness value goes first, then the next and so on
	static fn get_topness() -> float


// We want to be able to combine multiple contexts, so we can just pass one object to the llm handler, but with multiple variable pieces of information.
// a JoinedContext just concattenates contexts in order of their topness and optionally adds its own header and content
// If all subcontexts are null and content is null -> this context becomes also null
class JoinedContext:
	constructor(header, content, topness, sub_contexts...)


// Own role and name
class StaticContext

// Current round, number of players left, last phase type, current phase type, 
// next phase type, dead players (and their factions), role specific information 
// (seer: revealed factions, witch: used potions and on whom), which day it is
class GameNowContext


class PhaseGameContext
	// Contains context for *1* phase
	// offset: How many phases 'back' should we look? (e.g. offset=1 -> show last phase)
	// gives null context, if the phase is does not exist
	// optional: supports future phases for shits and giggles
	constructor(offset=0)

class PhaseTrustContext
	// Similar to PhaseGameContext but for trust labels

	// injected_trust: if we have some custom trust labels (e.g. llm 
	// generated them in a previous iteration) generated, please use these 
	// instead of the ones from the game. they come in the form of 
	// list[dict[PlayerName,Label]], where each phase gets one list entry
	constructor(offset=0, injected_trust=null)

// We can then just create multiple of these PhaseGameContext/PhaseTrustContext and join them into one combined context later

// Note: all context functions have to idempotent
```

An example context for the llm would look something like this:

```
# Static Data
You're role is: Villager

# Current Game State
Bob, Josh and Charls have been killed, all of them villagers. Jean is exiled, a werewolf.
It is the 3rd day, the village is currently discussing whom to exile next.

# Game State
## Last night <-- this would be 'the phase before the current one'
Charls died

## Current daytime discussion
[STEEVE] I AM SUPERMAN
[JAN] I AM SUPERGIRL
[BANA] i am not a supercat, just for the record. anyways, can we continue talking about who wants to kill us?

### Trust scores after the phase
You have noted down, that you trust steeve less than before and that with a high confidence (your new alignment trust score towards steeve is: 2)

```

## Inner Voice
The thing that is asked to provide trust advice

```
interface InnerVoice:
	fn ask(player_name, context, game_recods, phase_idx) -> TrustScores
	fn tool_description() -> str
	
	

// Gives scores from the game records
class HistoricInnerVoice

// its random
class RandomInnerVoice

// this needs to be a special case in `label_once` so it doesnt even define the toolcall
class NoInnerVoice


// ask a llm what it thinks with the same context as the asking agent
class AskMyselfInnerVoice


// Construct a custom context based on the game records and phase_idx instead of using the same one as the agent has been provided
class OtherContextInnerVoice
	constructor(context: Context)


```



## label_once
this is the heart of the code, it takes in all the components, provides them to the llm and returns the resulting labels.

```
fn label_conce(llm_provider, system_prompt: str, context: Context, inner_voice: InnerVoice, game_data: GameRecord, phase_idx: int) -> dict[PlayerName, Label], LLMCallInfo

class LLMCallInfo:
	// all the metadata, thinking if available, number and content of tool calls, ...

```

- define a toolcall to query the inner voice
	- the toolcall should just call the `InnerVoice` that has been passed to the function (converting the formats of course)
- define a toolcall to report results (trust labels) using a structured format (`structured_output` from langchain)
- materialize the context to a string
- call an agent with the systemprompt and the context
- allow an recursion limit=N_Players+1 (so we dont get while trues with endless loops)
	- catch those requests and call the llm once more with the full context it produced without the inner voice toolcall (no more recusion)
- return the trust labels and call info
# logging results
TODO

# Prompts
Prompts wont be hardcoded, since we want to switch them for testing, but we will just have a list of them in a `/prompts` folder.


# Visualization of logged results
# Integration
For now we just do a hardcoded integration, but I'd like to define a cli/ini based config loader later. the basic workflow would be:

```
provider = langchain_llm_provider_setup(some_key)

ctx = JoinedContext(StaticContext('josh'), GameContext, CurrentPhaseContext)
iv = RandomInnerVoice()
rec = GameRecord()
rec.read_from_files('results/games/something.xyz')

score, _ = label_once(...)


log_response('results/responses', 'chadGPT', ctx, iv, rec, score)


```


later on we can do more than one call and go through a full game