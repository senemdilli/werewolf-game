# Changelog

All notable, user-facing changes to this Werewolf game are documented here.
Dates are when the change landed on `main`. Loosely follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

## [2026-05-17]
### Added
- Day vote now auto-resolves after 60 seconds — the host can still force-resolve early.
- Players can chat during mayor election (initial and any mid-game re-election).
- Witch now waits for the werewolves to pick a target before her action panel reveals options, and is explicitly told who is under attack.

### Changed
- Server rejects witch actions submitted before the werewolves have voted (defence in depth for the new UI gate).

## [2026-05-11]
### Added
- "Skip vote" option in the day vote — if skip wins or ties for the top, no one is eliminated.
- New `day_result` phase: an 8-second announcement everyone sees together after voting, before night begins. Host can advance early.
- README replaces the create-next-app boilerplate with proper project documentation.

### Changed
- Duplicate names in the same room are suffixed `2`, `3`, etc. to disambiguate (e.g. `Alice`, `Alice2`, `Alice3`).
- CSV export `type` column relabeled for clarity: `message` → `chat`, `player_note` → `note`.
- Chat only auto-scrolls when you are already near the bottom. If you have scrolled up, a "↓ N new messages" pill appears and clicking it jumps to the latest message.

### Fixed
- Chat name colors leaked roles: werewolves' names appeared red to everyone. Roles are no longer broadcast with chat messages (they are still persisted to the database for research export).

## [2026-05-06]
### Added
- `/how-to-play` page with roles, game flow, and rules.
- Wolf-emoji SVG favicon replaces the default Next.js icon.

## [2026-05-05]
### Added
- First playable build of the multiplayer Werewolf game:
  - Lobby with 6-character room codes; 4–12 players per room.
  - Roles: Werewolf, Seer, Witch, Villager.
  - Elected Mayor with double-weight day votes, plus automatic re-election when the Mayor dies.
  - Full game loop: lobby → role reveal → night → mayor election → day discussion → day vote → repeat.
  - Werewolf-only night chat routed through a private Socket.IO channel.
  - Seer investigations delivered as private events (not via chat).
  - Witch potions: one heal and one kill, each usable once per game.
  - Phase timers (2 min day discussion, 60 s mayor election) with host force-advance.
  - Ready system: game auto-starts when all players are ready (minimum 4), and the host can force-start.
  - Host transfer in lobby and in-game on host disconnect.
  - Private per-player notes saved per phase/round — never broadcast, stored for research.
  - Admin dashboard at `/admin` (password-gated) with CSV export of chat, notes, and night actions.
- Stack: Next.js 16, React 19, Socket.IO, Prisma 7 / PostgreSQL, Redis, Tailwind 4. Deployable via Railway or Docker Compose.
