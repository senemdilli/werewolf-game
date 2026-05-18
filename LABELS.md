One or more labels can be created after each event.

## Label
```
// The main event that changed the trust factor
IN THE EVENT <evt_id>

// An action that happened during the event
THE ACTION OF <action_id> <args[]>

[INCREASES|DECREASES] MY TRUST [SLIGHTLY|SOMEWHAT|SIGNIFICANTLY]

// Players effected (one event can change trust in multiple persons)
TOWARDS <player_id[]>

// In regards to *what* is the trust effected?
IN REGARDS TO <trust_category>

// Previous events that have lead to this decision
BEAUSE OF <(evt_id | label_id)[]>

// The actual "Thinking" process
WITH THE REASONING THAT <free text>.


// New absolute assessment of trust towards a player
I HAVE NOW [HIGH|NEUTRAL|LOW] TRUST TOWARDS <player_id>.
```

## Events
An event is something that happened in the game:
- Messages sent by players
- Meta events
	- Exiles
	- Deaths
	- Votes (werewolves killing, mayor, exiles)
	- Villagers nighttime actions
		- Seer: Faction reveals
		- Witch: Death announcement, potion usage
	- Start/end of day-/nighttime


## Actions
Anything that a player can perform in the werewolf game:
- X voted to kill Y
- X voted for Y to be mayor
- X accused Y of being a werewolf
- X accused Y of not being a seer
- X accused Y of lying
- X accused Y of manipulating
- X did not respond
- X contradicted themselves
- X supports Y
- X betrayed Y
- ...

## Trust category
Some statement/relationship in the werewolf game that can be referenced in a structured way. Something that the player wants to be true, but assigns a trustworthiness to the assertion.
- For villagers:
	- Is a villager
	- Is a witch
	- Is a seer
	- Is not a werewolf
- For werewolves:
	- The other werewolf will not betray me
- ...


## Questions
- Do we add free text options to both actions and trust categories to allow custom labels? Do we want to gather additional labels through free text to expand the existing ones?
- Do we want to measure absolute or relative trust?
