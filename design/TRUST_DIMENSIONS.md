# Multidimensional Trust Model & Theoretical Foundations

This document details the theoretical foundation, academic literature citations, and definitions for the three perceived trust dimensions used across the Werewolf research platform: **Alignment**, **Information Trust**, and **Consistency**.

---

## Theoretical Overview

The trust labels form the foundation for the comparison of human and LLM trust assessments. Instead of using one general trust score, we divide perceived trust into three dimensions: Alignment, Information Trust, and Consistency. This follows prior work that describes interpersonal trust as a multidimensional construct rather than a single global judgment **[3]**. In complex social situations, people may trust another person in one respect while distrusting them in another **[3]**. For Werewolf, this distinction is important because players must judge not only whether someone is on their team, but also whether their information is useful and whether their behavior remains consistent over time.

---

## The Three Trust Dimensions

### 1. Goal Alignment (`alignment`)

Alignment describes whether a player believes that another player has goals compatible with their own. It is based on concepts such as benevolence, concern, and goal compatibility **[1, 6, 7]**. In general trust research, benevolence means that the trusted person is expected to care about the trustor’s interests and not exploit their vulnerability **[1, 5, 8]**. In Werewolf, this is adapted to the team-based structure of the game. A high Alignment score means that the target player is perceived as likely pursuing the same win condition, while a low score indicates that the player may be hostile or deceptive.

### 2. Information Trust (`information`)

Information Trust describes whether a player considers another player’s claims, observations, and reasoning to be reliable and useful. This dimension is adapted from epistemic trust, testimony reliability, and cognitive competence **[1, 2, 5]**. In Werewolf, this distinction is necessary because a player’s information quality does not always match their team alignment. For example, a villager may make an incorrect deduction, while a werewolf may state true information to gain credibility. Therefore, Information Trust measures how much a player relies on the target’s information for making game decisions, independently from whether the target is believed to be on the same team.

### 3. Consistency Trust (`consistency`)

Consistency describes whether a player behaves predictably and without contradiction over time. This dimension is grounded in concepts such as predictability, dependability, and behavioral integrity **[1, 4, 8]**. Predictability refers to recurrent behavior that allows others to form expectations about future actions **[4]**. In Werewolf, consistency is especially relevant because deception can lead to contradictions, unexplained vote switches, fabricated claims, or unstable alliances. A high Consistency score means that a player’s chat messages, votes, and claims appear coherent over time, while a low score indicates behavior that is volatile or contradictory.

---

## Rating Scales & Confidence Values

Each trust label can contain a Likert scale score from 1 to 7 for any of the three dimensions. The score represents the current trust assessment at that point in the game. In addition, each dimension includes a confidence value (`LOW_CONFIDENCE`, `MEDIUM_CONFIDENCE`, `HIGH_CONFIDENCE`), which indicates how certain the player is about the corresponding trust assessment.

Example trust label format:

```json
{
  "reasoning": "The player seems to support the village and gave useful information, but changed their voting target without fully explaining why.",
  "alignment": {
    "trust": "AGREE",
    "confidence": "MEDIUM_CONFIDENCE"
  },
  "information": {
    "trust": "AGREE",
    "confidence": "MEDIUM_CONFIDENCE"
  },
  "consistency": {
    "trust": "NEUTRAL",
    "confidence": "LOW_CONFIDENCE"
  }
}
```

---

## Academic References

* **[1]** Sekhon, H., Ennew, C., Kharouf, H., & Devlin, J. (2014). Trustworthiness and trust: influences and implications. *Journal of Marketing Management*, 30(3-4), 409-430.
* **[2]** Koenig, M. A., & Harris, P. L. (2007). The basis of epistemic trust: Reliable testimony or reliable sources?. *Episteme*, 4(3), 264-284.
* **[3]** Lewicki, R. J., McAllister, D. J., & Bies, R. J. (1998). Trust and distrust: New relationships and realities. *Academy of Management Review*, 23(3), 438-458.
* **[4]** Rempel, J. K., Holmes, J. G., & Zanna, M. P. (1985). Trust in close relationships. *Journal of Personality and Social Psychology*, 49(1), 95.
* **[5]** Malle, B. F., & Ullman, D. (2021). A multidimensional conception and measure of human-robot trust. In *Trust in Human-Robot Interaction* (pp. 3-25). Academic Press.
* **[6]** Hardin, R. (Ed.). (2004). *Distrust*. Russell Sage Foundation.
* **[7]** Jones, K. (2012). Trustworthiness. *Ethics*, 123(1), 61-85.
* **[8]** Lee, M. A., Alarcon, G. M., & Capiola, A. (2022). “I think you are trustworthy, need I say more?” the factor structure and practicalities of trustworthiness assessment. *Frontiers in Psychology*, 13, 797443.
