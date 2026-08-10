# Hidden-phase comprehension benchmark

- Answer model: `gemma4:31b`
- Judge model: `mistral-large:123b-instruct-2411-q6_K`
- Temperature: 0.0
- Setups found: 12 / 12

## Per-setup accuracy

| Game | Player | Role | Hidden phase | Kind | Objective | Speculative | Overall |
|------|--------|------|--------------|------|-----------|-------------|---------|
| 44UT6Y | Blue | Werewolf | h3 | Morning | 5/6 (83.3%) | 0/2 (0.0%) | 62.5% |
| 44UT6Y | Brown | Seer | h5 | Evening | 6/6 (100.0%) | 1/1 (100.0%) | 100.0% |
| 5NOHGS | Cyan | Witch | h0 | Morning | 5/6 (83.3%) | 2/2 (100.0%) | 87.5% |
| 5NOHGS | White | Villager | h5 | Evening | 5/6 (83.3%) | 1/1 (100.0%) | 85.7% |
| 928B2K | Yellow | Werewolf | h3 | Morning | 4/6 (66.7%) | 2/2 (100.0%) | 75.0% |
| 928B2K | Cyan | Villager | h5 | Evening | 5/6 (83.3%) | 0/1 (0.0%) | 71.4% |
| CCUTH3 | Beige | Werewolf | h3 | Morning | 4/6 (66.7%) | 2/2 (100.0%) | 75.0% |
| CCUTH3 | Purple | Seer | h5 | Evening | 6/6 (100.0%) | 0/1 (0.0%) | 85.7% |
| T5AVSL | Orange | Werewolf | h3 | Morning | 6/6 (100.0%) | 2/2 (100.0%) | 100.0% |
| T5AVSL | Cyan | Seer | h5 | Evening | 5/6 (83.3%) | 1/1 (100.0%) | 85.7% |
| VOKIJD | Green | Witch | h0 | Morning | 6/6 (100.0%) | 1/2 (50.0%) | 87.5% |
| VOKIJD | Magenta | Villager | h8 | Evening | 6/6 (100.0%) | 1/1 (100.0%) | 100.0% |

## Objective accuracy by role

| Role | Mean objective | Setups |
|------|----------------|--------|
| Seer | 94.4% | 3 |
| Villager | 88.9% | 3 |
| Werewolf | 79.2% | 4 |
| Witch | 91.7% | 2 |

## Objective accuracy by phase kind

| Kind | Mean objective | Setups |
|------|----------------|--------|
| Evening | 91.7% | 6 |
| Morning | 83.3% | 6 |

## Headline

- Mean **objective** accuracy across 12 setups: **87.5%**
- Mean **speculative** accuracy across 12 setups: 70.8%

