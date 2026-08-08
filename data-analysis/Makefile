GAME_RECORDS ?= ../results/game-records
LLM_RESULTS ?= ../results/llm-labeling
params ?= {}
PARAMS ?= $(params)
RAW_HUMAN ?= 0
FULL_Y_SCALE ?= 0

.PHONY: install run run-tool

install:
	uv sync --extra dev

run:
	uv run python main.py agent

run-tool:
	@if [ -z "$(tool)" ]; then \
		echo "Usage: make run-tool tool=<tool-name> [params='{}'] [GAME_RECORDS=...] [LLM_RESULTS=...] [RAW_HUMAN=1] [FULL_Y_SCALE=1]"; \
		exit 2; \
	fi
	uv run python main.py tool "$(tool)" --params '$(PARAMS)' --game-records "$(GAME_RECORDS)" --llm-results "$(LLM_RESULTS)" $(if $(filter 1,$(RAW_HUMAN)),--raw-human,) $(if $(filter 1,$(FULL_Y_SCALE)),--full-y-scale,)