# Wolf IOSL 2026 — agent guide

This is the umbrella repo. Two things live here:

- `design/` — pre-implementation proposals (rules, label taxonomy, trust-measurement design). Read these for *intent*; they may diverge from the shipped code.
- `werewolf-game/` — the canonical implementation. When editing code here, `werewolf-game/AGENTS.md` has stack-specific conventions and gotchas.

For deploy: `scripts/mirror-to-github.sh` rewrites `werewolf-game/` as the root and force-pushes to GitHub for Railway to deploy from. See the script header for usage.
