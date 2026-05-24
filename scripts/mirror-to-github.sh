#!/usr/bin/env bash
#
# Mirror selected branches from this GitLab umbrella repo to the GitHub
# `senemdilli/werewolf-game` repo, rewriting them so that `werewolf-game/`
# becomes the new root. The GitHub repo then looks like a clean Next.js
# project (suitable for Railway etc. to deploy directly).
#
# Defaults: mirror `main` and `senem/dev`. Pass branch names as args to
# override (e.g. `scripts/mirror-to-github.sh main`).
#
# Required remotes (configure once with `git remote add` if missing):
#   gitlab → git@git.tu-berlin.de:snet-internal/wolf-iosl-2026.git  (source)
#   origin → git@github.com:senemdilli/werewolf-game.git            (target)
#
# This script ALWAYS force-pushes the GitHub branches — by design, since
# `git subtree split` produces new commit hashes every run.

set -euo pipefail

SUBDIR="werewolf-game"
SOURCE_REMOTE="gitlab"
TARGET_REMOTE="origin"

if [ $# -eq 0 ]; then
  BRANCHES=("main" "senem/dev")
else
  BRANCHES=("$@")
fi

# Refuse to run with a dirty working tree — `subtree split` and branch
# checkout can clobber uncommitted work otherwise.
if ! git diff --quiet || ! git diff --cached --quiet; then
  echo "ERROR: working tree is dirty. Commit or stash before mirroring." >&2
  exit 1
fi

# Sanity-check remotes exist.
for remote in "$SOURCE_REMOTE" "$TARGET_REMOTE"; do
  if ! git remote get-url "$remote" >/dev/null 2>&1; then
    echo "ERROR: git remote '$remote' is not configured." >&2
    exit 1
  fi
done

echo "Fetching from $SOURCE_REMOTE and $TARGET_REMOTE..."
git fetch "$SOURCE_REMOTE" --prune
git fetch "$TARGET_REMOTE" --prune

current_branch=$(git rev-parse --abbrev-ref HEAD)
echo "Current branch (will restore at end): $current_branch"

trap 'git checkout "$current_branch" >/dev/null 2>&1 || true' EXIT

for branch in "${BRANCHES[@]}"; do
  echo
  echo "═══ Mirroring $branch ═══"

  if ! git rev-parse --verify "$SOURCE_REMOTE/$branch" >/dev/null 2>&1; then
    echo "WARN: $SOURCE_REMOTE/$branch not found on source — skipping." >&2
    continue
  fi

  # Check out a local copy of the source branch (reset to remote HEAD).
  git checkout -B "$branch" "$SOURCE_REMOTE/$branch"

  # Synthetic branch name for the subtree split result.
  synth="_mirror/$(echo "$branch" | tr / _)"
  git branch -D "$synth" >/dev/null 2>&1 || true

  echo "Splitting $SUBDIR/ as the new root..."
  git subtree split -P "$SUBDIR" -b "$synth"

  echo "Force-pushing to $TARGET_REMOTE/$branch..."
  git push -f "$TARGET_REMOTE" "$synth:$branch"

  git branch -D "$synth" >/dev/null 2>&1 || true
done

echo
echo "✓ Mirror complete. GitHub repo now reflects $SUBDIR/ at the root."
