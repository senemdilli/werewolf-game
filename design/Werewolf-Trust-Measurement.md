# Event-Based Trust Measurement for LLM Werewolf Agents

This document proposes a lightweight method for measuring how LLM agents update trust toward other agents during a game of Werewolf.

## Goal

Each agent maintains a private trust state toward every other player. After each relevant event, the agent updates this state and records why trust changed.

Relevant events include:

- messages
- accusations
- defenses
- votes
- vote switches
- role claims
- night events
- revealed roles
- round transitions

The core idea is:

> Trust should be measured as an event-based belief update: what changed, toward whom, in which category, by how much, and because of which evidence?

## Trust Categories

Each agent tracks four trust categories for every other player.

### `alignment_trust`

Belief that the target player is aligned with the observer's win condition.

- **High value:** likely on my team.
- **Low value:** likely hostile.

This is the most important category in Werewolf.

### `epistemic_trust`

Belief that the target player's claims, evidence, and reasoning are reliable.

A player can be honest but wrong, or deceptive but still make a true statement.

### `strategic_trust`

Willingness to rely on the target player's plans, votes, or coordination proposals.

This captures whether the observer would actually follow the player's strategy.

### `consistency_trust`

Belief that the target player's behavior is consistent over time.

This is useful because deception often creates contradictions, unexplained vote switches, or inconsistent claims.

## Scores

All trust scores are numeric values in `[0.0, 1.0]`.

- `0.0` = no trust
- `0.5` = neutral / uncertain
- `1.0` = complete trust

Each target also has a confidence score in `[0.0, 1.0]`.

Confidence is separate from trust. For example, an agent may have high trust but low confidence if the evidence is weak.

## Trust State

Each agent maintains a private absolute trust state.

```json
{
  "game_id": "game_001",
  "observer": "player_1",
  "after_evt_id": "evt_24",
  "trust_state": {
    "player_2": {
      "alignment_trust": 0.72,
      "epistemic_trust": 0.61,
      "strategic_trust": 0.58,
      "consistency_trust": 0.67,
      "confidence": 0.55
    },
    "player_3": {
      "alignment_trust": 0.42,
      "epistemic_trust": 0.48,
      "strategic_trust": 0.36,
      "consistency_trust": 0.39,
      "confidence": 0.62
    }
  }
}
```

## Trust Update Log

After each relevant event, the agent records relative trust changes.

```json
{
  "game_id": "game_001",
  "round": 2,
  "phase": "day",
  "evt_id": "evt_24",
  "observer": "player_1",
  "updates": [
    {
      "target": "player_3",
      "action_id": "vote_switch",
      "action_args": {
        "from": "player_5",
        "to": "player_2"
      },
      "trust_category": "alignment_trust",
      "previous_score": 0.56,
      "direction": "decrease",
      "magnitude_label": "moderate",
      "delta": -0.14,
      "new_score": 0.42,
      "new_label": "low",
      "confidence": 0.62,
      "supporting_evidence": ["evt_24"],
      "contradicting_evidence": ["evt_17"],
      "rationale": "The late vote switch lacked a new justification and appears opportunistic. This lowers alignment trust, although the earlier accusation in evt_17 still provides some counterevidence."
    }
  ]
}
```

## Update Rules

The agent should decide the numeric delta itself, but must follow these rules:

1. Do not reset trust from scratch. Update from the previous trust state.
2. Only change trust when the latest event provides meaningful evidence.
3. Use small deltas for weak evidence.
4. Use large deltas only for strong evidence, such as direct contradictions, confirmed role information, or highly suspicious voting behavior.
5. If there is no meaningful evidence, set `delta = 0` and `direction = "unchanged"`.
6. `new_score` must equal `previous_score + delta`, clipped to `[0.0, 1.0]`.
7. `direction` must match the sign of `delta`.
8. For a low absolute delta change, provide a concise evidence-based rationale.
9. For a high absolute delta change, cite strong supporting evidence.
10. Include contradicting evidence when relevant.
11. Do not use hidden role information unless the agent legitimately knows it.

## Behavioral Validation

Stated trust should be compared with later behavior.

Track whether the agent:

- votes for a player
- votes with a player
- defends a player
- accuses a player
- follows a player's suggestion
- changes belief after a player's argument
- coordinates with a player

Example:

```json
{
  "observer": "player_1",
  "target": "player_3",
  "after_evt_id": "evt_24",
  "stated_alignment_trust": 0.42,
  "behavior": {
    "voted_for_target": true,
    "defended_target": false,
    "followed_target_vote": false,
    "accused_target": true
  }
}
```

This helps detect mismatches between explicit trust and actual gameplay behavior.

## Evaluation Metrics

Useful metrics after the game:

- **Trust accuracy:** Did agents trust teammates and distrust opponents?
- **Deception success:** Did werewolves gain high trust from villagers?
- **False suspicion rate:** Did villagers wrongly distrust other villagers?
- **Trust volatility:** How strongly did trust fluctuate across events?
- **Evidence sensitivity:** Which event types caused the largest trust changes?
- **Behavior-trust consistency:** Did agents act according to their stated trust?
- **Persuasion vulnerability:** How much did one agent's argument change another agent's trust?

## Summary

The system has three layers:

1. **Absolute trust state:** current trust toward every other player.
2. **Event-based trust updates:** how and why trust changed after an event.
3. **Behavioral validation:** whether later actions match the stated trust.

The main principle is:

> A meaningful trust measure should track not only what an agent says it trusts, but how that trust changes after evidence and whether later behavior reflects it.
