# Data Scientist Agent

## Questions

Questions for the LLM Analyser (like BI over the trust data)

-  Avg. delta between 2 trust types over a player type (villagers/werewolves) (eg informational trust and the alignment) over all games with a certain setup (with labels in the context; without labels in the context)
How does the delta between 2 trust types over a player type change across round
A labeller has produced labelling over the course a game for one player

- Plot the delta between the LLM/human labelling at each phase (single game)

- Same as before but from game 1 to game 20 (to see if it the delta evolved as the players got more expert)

- Compare how extreme the labelling of the LLMs are compared to the humans (assumption is that humans would rate 2/5, , 3/5, 4/5 avoiding the extremes BUT LLMs often go to the extremes 1/5, 5/5)

- Find correlation between liker value and confidence given by human VS llm (human put 7/7 only if they are confident; LLM may give 7/7 with LOW Confidence)

- Assumption we must capture 3 labelling scores: the raw labelling, the "advice" score form the inner trust voice and the merged result.

- Calculate delta between raw labelling score AND merged result where the inner trust voice was queried
Same as above but only where the "inner trust voice" prompt is "vague"/"precise"

---

## Specifications

- LLM (Ochestrator)

- Tool Registry

- Tool Template

- Frontend (Not the priority atm)

- RAG - For the Json trust annotations

- Tools:
    - Plotting
    - Correlation measurement
    - Delta Calculation
    - Data Comparison / Evaluation (Free text output by LLM -- either Orchestrator or dedicated agent)
    - Tool Creator Agent?

---

## Input

- CSV Game Data (probably not needed):
    - Chat History
    - Events

- **Json Trust Annotations**
