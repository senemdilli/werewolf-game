# Game export CSV

Format reference for files produced by `GET /api/admin/export/[gameId]` — the per-game event log downloaded from the admin dashboard. Filenames look like `game-<roomCode>-<gameIdPrefix>.csv` (e.g. `game-87ISR3-bc5fe029.csv`).

A single CSV holds the full event log of **one game**: chat lines, night actions, day votes, and any private player notes — interleaved into a flat row schema and sorted within each section by `created_at`.

## File format

- UTF-8, comma-delimited, LF line endings.
- Every field is wrapped in double quotes; embedded `"` is escaped as `""`.
- Single header row, then one row per event.
- No trailing newline.

## Columns

The header is fixed:

```
type,game_id,room_code,game_mode,winner,round,phase,player_name,player_role,target_name,content,is_system,timestamp
```

### Game-level (constant across every row in a file)

| Column      | Meaning                                                                  |
|-------------|--------------------------------------------------------------------------|
| `game_id`   | UUID of the `Game` record.                                               |
| `room_code` | Short human-facing code used to join the room (e.g. `87ISR3`).           |
| `game_mode` | `CLASSIC` or `ARENA`.                                                    |
| `winner`    | `VILLAGERS`, `WEREWOLVES`, or empty if the game ended without a winner.  |

### Per-event

| Column         | Meaning                                                                                                                                                                                                                       |
|----------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `type`         | Row kind: `chat`, `night_action`, `day_vote`, or `note`. Determines how `content` and `target_name` should be read.                                                                                                           |
| `round`        | Integer. Lobby / pre-game is `0`; the counter increments on every transition into night. So night N and the following day N share round N.                                                                                    |
| `phase`        | `DAY` or `NIGHT`. For `night_action` always `NIGHT`; for `day_vote` always `DAY`; for `chat` and `note` it's the phase active when the event was recorded.                                                                    |
| `player_name`  | Display name of the actor at the time of the event (may be a randomized color-name like `Lime` if `forceRandomNames` was on).                                                                                                 |
| `player_role`  | `WEREWOLF`, `VILLAGER`, `SEER`, `WITCH`, or empty. Empty for system chat lines and for any chat/note whose player record could not be resolved.                                                                               |
| `target_name`  | Name of the target player. Empty for `chat` and `note` (no target); set for `night_action` and `day_vote`.                                                                                                                    |
| `content`      | Type-dependent — see below.                                                                                                                                                                                                   |
| `is_system`    | `true` only on `chat` rows that were emitted by the server (phase banners like "Night 2 begins.", elimination announcements, etc.). Always `false` for `night_action`, `day_vote`, and `note`.                                |
| `timestamp`    | ISO 8601 UTC timestamp of the underlying record's `created_at` (e.g. `2026-06-27T19:14:03.221Z`).                                                                                                                             |

## `content` and `target_name` by row type

| `type`         | `target_name`              | `content`                                                                            |
|----------------|----------------------------|--------------------------------------------------------------------------------------|
| `chat`         | empty                      | The literal message text. System messages have `is_system=true`.                     |
| `night_action` | target player's name       | `ActionType`: `KILL` (wolves), `INVESTIGATE` (seer), `HEAL` (witch), `WITCH_KILL`.   |
| `day_vote`     | name being voted for       | `VoteType`: `EXILE` (lynch ballot) or `MAYOR` (mayor election).                      |
| `note`         | empty                      | The private note text the player wrote to themselves during the round.               |

## Ordering

Rows are grouped by section in this order: `chat`, `night_action`, `day_vote`, `note`. Within each section rows are ascending by `timestamp` (night actions also tiebreak by `round` first). Sort by `timestamp` if you need a true chronological replay across sections.

## Notes on data quality

- Bot / sandbox games are mixed in with real games; filter on `game.isSandbox` upstream if you need to exclude them.
- `player_role` on chat/note rows is the player's role at export time, not at the moment of the message — relevant only for late joiners or replaced socket sessions.
- `target_name` on `day_vote` is the name as cast at vote time; it will not retroactively update if the target's display name changes.
