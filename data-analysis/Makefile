GAME_RECORDS ?= ../results/game-records
LLM_RESULTS ?= ../llm-labeling/results/llm-labeling

install:
	uv sync --extra dev

run:
	uv run python main.py agent --game-records "$(GAME_RECORDS)" --llm-results "$(LLM_RESULTS)"