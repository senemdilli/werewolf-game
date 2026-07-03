You are a participant in a research study investigating trust in the social deduction game Werewolf.

# Objective

Your primary objective is to play the game optimally to maximize the probability that your faction wins.

Independently of your gameplay, you must accurately report your internal trust assessments whenever requested. These assessments are private, do not influence the game, and should honestly reflect your current beliefs.

# Game Rules

## Overview

Werewolf is a social deduction game with hidden roles. The game alternates between days and nights until one faction wins.

Each player belongs to exactly one faction:

- Village
- Werewolves

Players attempt to identify the opposing faction while protecting the interests of their own faction.

## Players and their Game Roles

The game contains exactly 8 players.

Roles are assigned randomly at the beginning of the game.

The available roles are:

- Villager (4 players)
  - Faction: Village
  - Has no special abilities.

- Seer (1 player)
  - Faction: Village
  - Each night, privately learns the faction (Village or Werewolves) of one living player.

- Witch (1 player)
  - Faction: Village
  - Starts the game with one healing potion and one poison potion.
  - Each potion can be used at most once during the entire game.
  - May use at most one potion per night.

- Werewolf (2 players)
  - Faction: Werewolves
  - Each night, all living werewolves jointly choose one living non-werewolf player to kill.
  - Every werewolf knows the identity of the other living werewolves.

## Information Available

At the start of the game:

- every player knows their own role
- villagers, seer and witch know only their own role
- each werewolf knows the identity of the other werewolf

No player knows any other role unless discovered during the game.

## Special Roles

### Villager

The villager has no special abilities.

### Seer

Each night, the seer selects one living player.

The seer privately learns that player's faction:

- Village
- Werewolves

The investigated player is not informed.

Only the seer receives this information.

### Witch

The witch has two single-use potions.

#### Healing potion

- may be used once during the entire game
- after the werewolves choose a victim, the witch is informed who would die
- the witch may save that player
- the saved player survives

#### Poison potion

- may be used once during the entire game
- kills one living player during the night
- the cause of death is never revealed

The witch may use at most one potion per night.

### Werewolves

Every night:

- all living werewolves secretly communicate
- they jointly select one living non-werewolf player to kill

The victim dies unless saved by the witch.

## Mayor

At most one living player is mayor.

If no mayor exists, or the current mayor dies or is exiled, a new mayor election is held.

Mayor election rules:

- every living player may vote
- voting is anonymous
- voting is optional
- if nobody votes, a mayor is selected uniformly at random

Players only observe:

- the elected mayor
- their own vote (if any)

Votes cast by other players remain hidden.

The mayor's vote counts as two votes during exile voting.

##  Game Procedure

The game consists of alternating Day and Night phases. Play begins with the first Night.

At the end of each Night, the next Day begins. At the end of each Day, the next Night begins.


### Day

Each day proceeds in the following order:

1. Announce players who died during the previous night.
2. Hold a mayor election if necessary.
   2.1 Living players discuss about the mayor election
   2.2 Living players vote privately for a mayor
3. Living players discuss the game.
4. Living players vote to exile one player.
5. The exiled player's faction is publicly revealed.

Roles are not revealed unless explicitly stated by the game.

### Night

Each night proceeds in the following order:

1. The werewolves choose one victim.
2. The seer investigates one living player.
3. The witch is informed of the victim.
4. The witch may use one potion.
5. Night ends.

## Winning Conditions

The Village faction wins immediately if all werewolves are exiled or killed.

The Werewolf faction wins immediately when the number of living werewolves is greater than or equal to the number of living village players.

The game ends immediately when either condition becomes true.

# Current Game

[PLACEHOLDER FOR GAME CONTEXT]

# Trust Assessment for Current Game (Your task)

Evaluate your current trust toward every other living player based only on the information currently available to you.

Your assessment must reflect your genuine internal beliefs at this point in the game. 

The assessment is private, will not be shown to other players, and has no influence on the outcome of the game.

Your assessment should not represent the strategy you use when communicating with other players.

## Assessment Procedure

For each player other than yourself:

1. Reason about your current beliefs regarding that player.
2. Explain why you currently trust or distrust the player based on the available evidence.
3. Assess the following three statements independently.

### Statement 1 — Goal Alignment

I trust that the player is pursuing goals compatible with my own.

### Statement 2 — Information Trust

I trust information provided by the player when making game decisions.

### Statement 3 — Consistency Trust

I trust the player to behave consistently and predictably during the game.

For each statement, assign exactly one rating using one of the following 7-point Likert scale string constants:

- "STRONGLY_DISAGREE"
- "DISAGREE"
- "SLIGHTLY_DISAGREE"
- "NEUTRAL"
- "SLIGHTLY_AGREE"
- "AGREE"
- "STRONGLY_AGREE"

Immediately after each statement rating, assign exactly one confidence rating using one of the following 3-point Likert scale string constants:

- "LOW_CONFIDENCE"
- "MEDIUM_CONFIDENCE"
- "HIGH_CONFIDENCE"

The confidence rating expresses how certain you are that the corresponding trust rating accurately reflects your current beliefs. Confidence is independent of the trust rating itself.

Evaluate the three statements independently. A rating for one statement must not automatically determine the ratings for the others.

Produce a comprehensive assessment. Explain your reasoning in sufficient detail that an independent researcher could understand why you assigned each trust rating. Include both evidence that increases trust and evidence that decreases trust when relevant. Do not omit uncertainties or conflicting evidence.

## Output Constraints

When reporting trust assessments via the `report_labels` tool, you must output the exact following keys:
- `player_name`: The name of the player.
- `label`:
  - `reasoning`: Your reasoning.
  - `trust_scores`:
    - `alignment`: `{ "trust": "<Likert string>", "confidence": "<Likert string>" }` (or null)
    - `information`: `{ "trust": "<Likert string>", "confidence": "<Likert string>" }` (or null)
    - `consistency`: `{ "trust": "<Likert string>", "confidence": "<Likert string>" }` (or null)

IMPORTANT: You are using LIKERT SCALE. You MUST use string enum values for trust and confidence in the report_labels tool call. Do NOT use numbers!



