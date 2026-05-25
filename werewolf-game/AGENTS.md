# Werewolf game — agent guide

Conventions and non-obvious gotchas for working inside `werewolf-game/`. Read
this before making changes; the items below have all caused real bugs.

## Stack at a glance

- **Next.js 16** (App Router), React 19, Tailwind 4
- **Custom Node entrypoint** (`server.ts`) — HTTP + Socket.IO on the same port (this is **not** a serverless deploy)
- **Live state**: Redis (24h TTL per room, see `lib/redis.ts` + `server/game/state.ts`)
- **Persisted state**: PostgreSQL via Prisma 7 — for research export only, never read back into gameplay
- **Auth**: httpOnly cookie + middleware gate for `/admin` and `/api/admin/*`

> Next.js 16 has breaking changes from earlier versions — APIs, conventions,
> and file structure may differ from training data. Check
> `node_modules/next/dist/docs/` before reaching for patterns you remember.

## Mental model — two state stores

| | Redis (`game:<roomCode>`) | Postgres |
|-|-|-|
| **What** | Live `GameState` — phase, votes, conversation, labelingBreak, etc. | Immutable event log: messages, night actions, labels, games, players |
| **Lifetime** | 24h TTL | Forever (or until deleted) |
| **Read by gameplay?** | Every tick | Never — research export only |
| **Touched by** | `server/game/state.ts` + handlers | `lib/prisma.ts` + handlers |

When adding a feature, ask: does it need to drive gameplay (Redis) or just be analyzable later (Postgres)? Usually both — see how `persistSystem` does it.

## Phase has two representations — this is a footgun

- `Phase` (TypeScript, `types/game.ts`): **lowercase, granular** union — `'lobby' | 'role_reveal' | 'night' | 'mayor_advocacy' | 'mayor_election' | 'day_discussion' | 'day_vote' | 'day_result' | 'game_over'`
- `Phase` (Prisma enum, `schema.prisma`): **uppercase, coarse** — `DAY | NIGHT`

Server code carries both, and they don't always match (a system message about the dawn is *written* during `state.phase === 'night'` but is conceptually a `DAY` event). Always think about which one you mean. `persistSystem(io, state, content, dbPhase)` takes the coarse `dbPhase` explicitly for this reason.

## `persistSystem` broadcasts to clients now

Every call to `persistSystem` writes to Postgres **and** emits `chat:message`
with `isSystem: true` to everyone in the room. This is what the trust-labeling
panel uses to populate its event picker, and what the Chat component renders
as italic gray messages.

If you add a new system message:

- Call `persistSystem(io, state, content, dbPhase)` — never `prisma.message.create({...isSystem: true...})` directly.
- The message will be visible in every player's chat. Plan content accordingly (no leaking role info beyond what's already revealed via `state.lastEliminated` etc.).

## Labels are write-only from the player UI

Per spec: a player **never** sees their own past labels back. Do not add a "your saved labels" list to `LabelPanel` or `GameRoom` without checking the research design first. The data still lives in Postgres and is accessible via the admin JSON export at `/api/admin/export/[gameId]/labels`.

## Don't import `@prisma/client` types into shared `types/game.ts`

Anything in `types/game.ts` ends up in both the server and the client bundle.
Importing `@prisma/client` there leaks server-only types and dependencies into the browser. For shared enums, use TS const-string-unions (lowercase) and convert to Prisma enums (uppercase) only in handler code — see `server/socket/handlers/labels.ts` for the pattern.

## Other things worth knowing

- Players join `room:<roomCode>` (everyone) and werewolves additionally join `wolves:<roomCode>` (private night chat). `io.to('room:'+roomCode).emit(...)` reaches everyone in the room.
- Per-game `Player.id` is the in-memory ID, but Prisma persists a separate row per game-session. Resolve via `prisma.player.findFirst({ where: { gameId, name } })` — see existing handlers.
- The `phaseTimers` map in `server/socket/handlers/game.ts` holds exactly one timer per room. The labeling break temporarily replaces it; the helper `schedulePhaseTimer` knows how to restart the right end-of-phase function based on `state.phase`.
- Arena mode and Classic mode coexist in the same code; check `state.gameMode` before branching. Most logic lives in `server/socket/handlers/game.ts` with explicit `if (state.gameMode === 'arena')` blocks.
- Apply schema changes with `npm run db:push`. The Docker container does this on boot — see `Dockerfile`.

## Where to add things

| You want to add… | Touch… |
|-|-|
| A new player action (socket event) | `types/game.ts` (event signature) + new/existing handler in `server/socket/handlers/` + register in `server/socket/index.ts` |
| A new UI panel during a phase | `components/game/<Panel>.tsx` + render conditionally in the phase component (`NightPhase`, `DayPhase`, etc.) or `GameRoom.tsx` |
| Server-driven UI state | Field on `GameState` (`types/game.ts`) → init in `server/game/state.ts:createInitialState` → expose in `buildClientState` (carefully — per-player view filtering happens here) |
| Research data | New Prisma model (or column) → new write site in the relevant handler → new column/row in the admin CSV/JSON export route |
