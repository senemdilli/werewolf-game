Based on: *Werewolf Arena: A Case Study in LLM Evaluation via Social Deduction*

# Nighttime
- Actions of special roles happen:
	1. Werewolves choose one person to kill
		- Not mentioned how they build consensus in the paper
		- IDEA:
			- If only a single werewolf lives, they just choose
			- Multiple werewolves get 3 rounds of voting for a person to kill (no talking). Nobody dies if they disagree after the last round. To reduce confusion, werewolves vote sequentially wit a random werewolf starting (allows voting for the same person at the end to not accidentally kill nobody). 
			- Werewolves are allowed to vote for killing nobody
	2. Witch is notified about a death (if one happend) and is allowed to use a potion.
	3. Seer is allowed to reveal the faction of one living player to themselves
- Announce outcomes of the night
# Daytime
1. If no mayor exists or they died a vote for a new mayor is held
	- Mayors not present in the paper
	- IDEA:
		- Every player *can* send 1 message advocating for themselves to become mayor (random speaking order)
		- 4 (half of a day) rounds of conversation for the mayoral election
		- Every player votes for a mayor
		- Results (and individual votes) are published
		- On ties:
			- A second round of votes between the candidates
			- Coin flip
2. Conversation
	-  8 rounds. In each round:
		- Everybody privately bids (from 1-5) how much they want to speak at the moment
		- The player with the highest bid is allowed to speak (send a message) next
		- On tie:
			- Random draw
			- Players mentioned in the last turn get a higher chance on being picked
	- Extensions:
		- Allow debates to end early (mentioned in the paper)
		- Allow debates to extend N more rounds if engagement is high (e.g. average bid is over 3)
3. Vote
	- Players vote for a person to be exiled from the village
	- Results are published
	- If  no player has more than one vote, nobody will be exiled
	- On tie:
		- Mayor decides the player to to exile

# Win conditions:
- Werewolf faction: Number of werewolves and villagers are equal
- Villager faction: All werewolves are dead
