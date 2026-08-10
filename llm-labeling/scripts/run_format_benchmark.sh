#!/usr/bin/env bash
#
# Reproducible context-format benchmark for the game-comprehension quiz.
#
# Runs the full 3-game x 4-format matrix, each setup repeated N times at a
# non-zero temperature, then writes per-setup aggregate.json/aggregate.md
# (mean +/- std overall and per question type).
#
# Usage (from the llm-labeling directory):
#   OLLAMA_URL=https://gpu.snet.tu-berlin.de/echelon/ollama \
#   ./scripts/run_format_benchmark.sh
#
# Override defaults via environment variables:
#   RUNS=30 ANSWER_MODEL=gemma4:31b JUDGE_MODEL=mistral-large:123b \
#   TEMPERATURE=0.7 ./scripts/run_format_benchmark.sh
#
set -euo pipefail

# --- Config (override via env) ------------------------------------------------
RUNS="${RUNS:-30}"
TEMPERATURE="${TEMPERATURE:-0.7}"
ANSWER_MODEL="${ANSWER_MODEL:-gemma4:31b}"
JUDGE_MODEL="${JUDGE_MODEL:-mistral-large:123b-instruct-2411-q6_K}"
OLLAMA_URL="${OLLAMA_URL:-https://gpu.snet.tu-berlin.de/echelon/ollama}"
HIDDEN_PHASE="${HIDDEN_PHASE:-0}"

# Resolve paths relative to this script so it can be run from anywhere.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
PY="${PYTHON:-${ROOT_DIR}/.venv/bin/python}"
CLI="${ROOT_DIR}/src/wolf_llm_labeling/quiz/cli.py"
QUIZ_DIR="${ROOT_DIR}/quizzes"

export PYTHONPATH="${ROOT_DIR}/src:${PYTHONPATH:-}"

# --- Experimental matrix ------------------------------------------------------
# "game.csv:player" triples; one representative player per game.
ALL_SETUPS=(
  "game-44UT6Y-d59e923e.csv:Blue"
  "game-5NOHGS-b57eee98.csv:Green"
  "game-T5AVSL-65a9d859.csv:Orange"
)
CHRONOLOGIES=(numeric timestamp)
LIST_STYLES=(plain dash)

# Optional filter: GAMES="44UT6Y" (or "44UT6Y,5NOHGS") runs only those games.
# Matches on the short room code in the game filename. Empty => all games.
GAMES="${GAMES:-}"
SETUPS=()
if [[ -z "${GAMES}" ]]; then
  SETUPS=("${ALL_SETUPS[@]}")
else
  filter=",${GAMES//[[:space:]]/},"          # normalise to ",A,B,"
  for s in "${ALL_SETUPS[@]}"; do
    code="$(echo "${s%%:*}" | cut -d- -f2)"   # e.g. 44UT6Y
    if [[ "${filter}" == *",${code},"* ]]; then
      SETUPS+=("${s}")
    fi
  done
  if [[ ${#SETUPS[@]} -eq 0 ]]; then
    echo "Error: GAMES='${GAMES}' matched no known games (44UT6Y, 5NOHGS, T5AVSL)." >&2
    exit 1
  fi
fi

echo "=============================================================="
echo " Context-format quiz benchmark"
echo "   answer model : ${ANSWER_MODEL}"
echo "   judge model  : ${JUDGE_MODEL}"
echo "   temperature  : ${TEMPERATURE}"
echo "   runs/setup   : ${RUNS}"
echo "   hidden phase : ${HIDDEN_PHASE}"
echo "   setups       : ${#SETUPS[@]} games x ${#CHRONOLOGIES[@]} x ${#LIST_STYLES[@]} = $(( ${#SETUPS[@]} * ${#CHRONOLOGIES[@]} * ${#LIST_STYLES[@]} ))"
echo "=============================================================="

mkdir -p "${QUIZ_DIR}"

for setup in "${SETUPS[@]}"; do
  game="${setup%%:*}"
  player="${setup##*:}"
  game_stem="${game%.csv}"
  short="$(echo "${game_stem}" | cut -d- -f2)"   # e.g. 44UT6Y

  for chrono in "${CHRONOLOGIES[@]}"; do
    for style in "${LIST_STYLES[@]}"; do
      player_lc="$(printf '%s' "${player}" | tr '[:upper:]' '[:lower:]')"
      tag="${player_lc}-h${HIDDEN_PHASE}-${short}-${chrono}-${style}"
      quiz_file="${QUIZ_DIR}/${tag}.json"

      echo
      echo "### Generating quiz: ${tag}"
      "${PY}" "${CLI}" generate \
        --game "${game}" \
        --player "${player}" \
        --hidden-phase "${HIDDEN_PHASE}" \
        --chronology "${chrono}" \
        --list-style "${style}" \
        --out "${quiz_file}"

      echo "### Running ${RUNS}x: ${tag}"
      "${PY}" "${CLI}" run "${quiz_file}" \
        --primary-model "${ANSWER_MODEL}" \
        --judge-model "${JUDGE_MODEL}" \
        --ollama-url "${OLLAMA_URL}" \
        --rules-file rules.md \
        --temperature "${TEMPERATURE}" \
        --runs "${RUNS}" \
        --run-tag "${tag}"
    done
  done
done

echo
echo "=============================================================="
echo " Benchmark complete. Aggregates per setup:"
echo "   ${ROOT_DIR}/results/quiz/<game>/<tag>-x${RUNS}/aggregate.md"
echo "=============================================================="
