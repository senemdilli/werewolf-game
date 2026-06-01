# **Prompting Outline**

## **Cognitive Architecture**
#### - layer-based architecture to model perceived game state and belief

### 1. Global Game State
<ul style="list-style-type: none;">
  <li>ground truth
   </li>
  <li>contains all information about past events and messages of the current ongoing game in detail
  </li>
</ul>

### 2. Observation Filter
<ul style="list-style-type: none;">
  <li>individual for every player/role
  </li>
  <li>proportion of the ground truth that the individual players can perceive, e.g. only the witch knows if heal potion still available 
   </li>
   <li>up to date, aggregated state of the game -> no history 
   </li>
</ul>


### 3. Memory Retrieval
<ul style="list-style-type: none;">
  <li>individual for every player
  </li>
  <li>proportion of the ground truth that the individual player can remember -> history
   </li>
  <li>should replicate human memory and contain incomplete information about events that reach far back or would be to insignificant for humans to remember
  </li>
</ul>

### 4. Belief State
<ul style="list-style-type: none;">
  <li>individual for every player
  </li>
  <li>current relationship of trust towards all players e.g. trust scores, confidence scores, (maybe role hypothesis)
   </li>
</ul>

### 5. Prompt Assemby
<ul style="list-style-type: none;">
  <li>forming of the context window based on all the building blocks
   </li>
</ul>

&nbsp;

## **Prompt Template Components**
```
{System Constraints}

• contains setting information and core rules/description of the werewolf game

{Role}

• contains game role

{Observed Game State}

• contains information about alive players, current state snapshot (no history), last event, current time, current voting (already placed votes from others) etc. -> should be after observation filter

{Belief State}

• contains the current trust measures for all players

{Retrieved Memory}

• contains retrieved memory with compressed information regarding past messages, votings etc. (imperfect / selective recall)

{Social Context}

• contains information about the current ongoing discussion (only relevant if discussion is happening)

{Task}

• contains current objective e.g. vote, speech urgency, public statement, optionally update beliefs etc.

{Output Format Definition}

• contains clearly defined expected output format for further processing
```

&nbsp;

## **Further Ideas for Prompt Template Components**

```
{Additional Claims}

• contains preprocessed information about claims from other players e.g. Text message: P2: "I trust P4 more than P3" to "P2 claims P4 is more trustworthy than P3" -> could help the llm recognize accusations
```