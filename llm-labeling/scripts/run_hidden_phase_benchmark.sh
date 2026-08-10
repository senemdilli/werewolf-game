#!/usr/bin/env bash
#
# Leave-one-phase-out comprehension benchmark (report matrix).
#
# 6 games x 2 setups = 12 quizzes. Each setup hides one eventful morning or
# evening phase and asks the answer model to reconstruct it from surrounding
# phases. Objective and speculative accuracy are reported separately.
#
# Usage (from the llm-labeling directory):
#   OLLAMA_URL=https://gpu.snet.tu-berlin.de/echelon/ollama \
#   ./scripts/run_hidden_phase_benchmark.sh
#
# Dry-run (generate quizzes only, no LLM calls):
#   GENERATE_ONLY=1 ./scripts/run_hidden_phase_benchmark.sh
#
# Override defaults via environment variables:
#   RUNS=1 TEMPERATURE=0.0 ANSWER_MODEL=gemma4:31b \
#   JUDGE_MODEL=mistral-large:123b-instruct-2411-q6_K \
#   GAMES=44UT6Y,5NOHGS ./scripts/run_hidden_phase_benchmark.sh
#
set -euo pipefail

# --- Config (override via env) ------------------------------------------------
RUNS="${RUNS:-1}"
TEMPERATURE="${TEMPERATURE:-0.0}"
ANSWER_MODEL="${ANSWER_MODEL:-gemma4:31b}"
JUDGE_MODEL="${JUDGE_MODEL:-mistral-large:123b-instruct-2411-q6_K}"
OLLAMA_URL="${OLLAMA_URL:-https://gpu.snet.tu-berlin.de/echelon/ollama}"
CHRONOLOGY="${CHRONOLOGY:-numeric}"
LIST_STYLE="${LIST_STYLE:-plain}"
GENERATE_ONLY="${GENERATE_ONLY:-0}"
GAMES="${GAMES:-}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
PY="${PYTHON:-${ROOT_DIR}/.venv/bin/python}"
CLI="${ROOT_DIR}/src/wolf_llm_labeling/quiz/cli.py"
QUIZ_DIR="${ROOT_DIR}/quizzes/hidden-phase"
SUMMARY_SCRIPT="${ROOT_DIR}/scripts/summarize_hidden_phase_benchmark.py"

export PYTHONPATH="${ROOT_DIR}/src:${PYTHONPATH:-}"

# --- Experimental matrix ------------------------------------------------------
# Fields: game.csv:player:role:hidden_phase:anchor_phase:phase_kind
# Roles cover Werewolf / Villager / Seer / Witch. Phase kinds cover Morning
# (deaths / mayor) and Evening (exile). Observer is alive in the hidden phase.
ALL_SETUPS=(
  # game-44UT6Y — mid length (9 phases)
  "game-44UT6Y-d59e923e.csv:Blue:Werewolf:3:4:Morning"
  "game-44UT6Y-d59e923e.csv:Brown:Seer:5:6:Evening"

  # game-5NOHGS — short (7 phases)
  "game-5NOHGS-b57eee98.csv:Cyan:Witch:0:1:Morning"
  "game-5NOHGS-b57eee98.csv:White:Villager:5:6:Evening"

  # game-T5AVSL — long (12 phases)
  "game-T5AVSL-65a9d859.csv:Orange:Werewolf:3:4:Morning"
  "game-T5AVSL-65a9d859.csv:Cyan:Seer:5:6:Evening"

  # game-928B2K — short (7 phases)
  "game-928B2K-7ced9961.csv:Yellow:Werewolf:3:4:Morning"
  "game-928B2K-7ced9961.csv:Cyan:Villager:5:6:Evening"

  # game-VOKIJD — long (12 phases)
  "game-VOKIJD-d25f0264.csv:Green:Witch:0:1:Morning"
  "game-VOKIJD-d25f0264.csv:Magenta:Villager:8:9:Evening"

  # game-CCUTH3 — medium (10 phases)
  "game-CCUTH3-352fd9ba.csv:Beige:Werewolf:3:4:Morning"
  "game-CCUTH3-352fd9ba.csv:Purple:Seer:5:6:Evening"
)

SETUPS=()
if [[ -z "${GAMES}" ]]; then
  SETUPS=("${ALL_SETUPS[@]}")
else
  filter=",${GAMES//[[:space:]]/},"
  for s in "${ALL_SETUPS[@]}"; do
    game="${s%%:*}"
    code="$(echo "${game%.csv}" | cut -d- -f2)"
    if [[ "${filter}" == *",${code},"* ]]; then
      SETUPS+=("${s}")
    fi
  done
  if [[ ${#SETUPS[@]} -eq 0 ]]; then
    echo "Error: GAMES='${GAMES}' matched no setups." >&2
    echo "Known codes: 44UT6Y, 5NOHGS, T5AVSL, 928B2K, VOKIJD, CCUTH3" >&2
    exit 1
  fi
fi

echo "=============================================================="
echo " Hidden-phase comprehension benchmark"
echo "   answer model : ${ANSWER_MODEL}"
echo "   judge model  : ${JUDGE_MODEL}"
echo "   temperature  : ${TEMPERATURE}"
echo "   runs/setup   : ${RUNS}"
echo "   chronology   : ${CHRONOLOGY}"
echo "   list style   : ${LIST_STYLE}"
echo "   setups       : ${#SETUPS[@]}"
echo "   generate only: ${GENERATE_ONLY}"
echo "=============================================================="
echo
echo "Matrix:"
printf "  %-22s %-8s %-9s %-7s %-7s %s\n" "GAME" "PLAYER" "ROLE" "HIDDEN" "ANCHOR" "KIND"
for s in "${SETUPS[@]}"; do
  IFS=':' read -r game player role hidden anchor kind <<< "${s}"
  short="$(echo "${game%.csv}" | cut -d- -f2)"
  printf "  %-22s %-8s %-9s %-7s %-7s %s\n" "${short}" "${player}" "${role}" "h${hidden}" "a${anchor}" "${kind}"
done
echo

mkdir -p "${QUIZ_DIR}"

for s in "${SETUPS[@]}"; do
  IFS=':' read -r game player role hidden anchor kind <<< "${s}"
  game_stem="${game%.csv}"
  short="$(echo "${game_stem}" | cut -d- -f2)"
  player_lc="$(printf '%s' "${player}" | tr '[:upper:]' '[:lower:]')"
  tag="${player_lc}-h${hidden}-${short}-${CHRONOLOGY}-${LIST_STYLE}"
  quiz_file="${QUIZ_DIR}/${tag}.json"

  echo
  echo "### [${kind}] Generating quiz: ${tag}  (${role})"
  "${PY}" "${CLI}" generate \
    --game "${game}" \
    --player "${player}" \
    --hidden-phase "${hidden}" \
    --anchor-phase "${anchor}" \
    --chronology "${CHRONOLOGY}" \
    --list-style "${LIST_STYLE}" \
    --out "${quiz_file}"

  if [[ "${GENERATE_ONLY}" == "1" ]]; then
    continue
  fi

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

echo
echo "=============================================================="
if [[ "${GENERATE_ONLY}" == "1" ]]; then
  echo " Generation complete. Quizzes written to:"
  echo "   ${QUIZ_DIR}/"
else
  echo " Benchmark complete."
  echo "   Per-setup results: ${ROOT_DIR}/results/quiz/<game>/<tag>/"
  if [[ -f "${SUMMARY_SCRIPT}" ]]; then
    echo
    echo "### Writing report summary"
    "${PY}" "${SUMMARY_SCRIPT}" \
      --results-dir "${ROOT_DIR}/results/quiz" \
      --out "${ROOT_DIR}/results/quiz/HIDDEN_PHASE_REPORT.md"
  fi
fi
echo "=============================================================="
