# Werewolf

A multiplayer Werewolf (Mafia) social deduction game. Built as a research tool for studying chat dynamics, deception, and group decision-making — every message, vote, night action, and private player note is logged for later analysis.

## Features

- **5 roles**: Werewolf, Seer, Witch, Villager, plus an elected Mayor whose vote counts double
- **Real-time multiplayer** over WebSockets — 4 to 12 players per room
- **Full game loop**: lobby → role reveal → night → mayor election → day discussion → day vote → day result → repeat
- **Skip vote**: the village can collectively choose not to eliminate anyone
- **Private notes**: each player can record their suspicions per phase/round (visible only to them, stored for research)
- **Voice-to-Text (Speech-to-Text)**: Speak your reasonings in the labeling panel. Supports low-latency real-time streaming, quick EN/DE language switching, a robust automatic HTTP fallback for firewalled networks, and 6-second AI silence detection.
- **Sandbox/Testing Mode**: Host can toggle sandbox mode at room creation to automatically fill empty spots with bots, allowing solo-testing of all game phases without needing 4 tabs.
- **Werewolf-only night chat** routed through a private Socket.IO room
- **Seer investigations** delivered as private events that don't pass through chat
- **Witch potions**: one heal, one kill — each usable once per game, with full visibility of the werewolves' chosen victim
- **Phase timers** for day discussion and mayor election, with host force-advance
- **Auto-start when all ready** (with a force-start escape hatch for the host)
- **Admin dashboard** (password-protected) with CSV export of all game data

## Stack

| Layer | Choice |
|---|---|
| Frontend | Next.js 16 (App Router), React 19, Tailwind 4 |
| Server | Custom Node entrypoint (`server.ts`) — HTTP + Socket.IO on the same port |
| State | Redis (24h TTL per room) for live game state |
| Persistence | PostgreSQL via Prisma 7 — games, players, messages, night actions, notes |
| Auth | httpOnly cookie + middleware gate for `/admin` and `/api/admin/*` |
| Deploy | Railway (Postgres + Redis plugins) or Docker Compose |

## Project layout

```
app/
  page.tsx                  Home — create/join/admin/how-to-play
  how-to-play/page.tsx      Static rules & roles page
  room/[code]/page.tsx      Game room shell
  admin/                    Password-gated dashboard + CSV export
  api/admin/                Auth + export endpoints
components/game/
  GameRoom.tsx              Phase router
  Lobby, RoleReveal,        Per-phase screens
  NightPhase, MayorElection,
  DayPhase, DayResult, GameOver
  Chat.tsx                  Scroll-aware chat with unread pill
  NotePanel.tsx             Floating private-notes panel
server/
  game/
    state.ts                Redis-backed state + per-player view filtering
    roles.ts                Role assignment, win condition, vote resolution
  socket/
    index.ts                Handler wiring
    handlers/               room, game, chat, notes
types/game.ts               Shared event & state types (client + server)
prisma/schema.prisma        Game / Player / Message / NightAction / PlayerNote
server.ts                   HTTP + Socket.IO bootstrap
middleware.ts               Admin route guard
```

## Local development

### With Docker (recommended)

Everything — app, Postgres, Redis — runs together:

```bash
docker compose up --build
```

Open <http://localhost:3001>. The admin password is set in `docker-compose.yml` (`ADMIN_SECRET`).

### Without Docker

You need a running Postgres and Redis. Then:

```bash
cp .env.example .env       # fill in DATABASE_URL, REDIS_URL, ADMIN_SECRET
npm install
npm run db:push            # apply Prisma schema
npm run dev
```

App will be on <http://localhost:3000>.

## Environment variables

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | PostgreSQL connection string |
| `REDIS_URL` | Redis connection string |
| `ADMIN_SECRET` | Password for the `/admin` dashboard |
| `DEEPGRAM_API_KEY` | Deepgram API Key for Voice-to-Text transcription (optional, enables speech recognition) |
| `NEXT_PUBLIC_APP_URL` | Public origin — used for the Socket.IO CORS allowlist |
| `PORT` | HTTP port (Railway sets this automatically) |

## How the game flows

1. **Lobby** — players join via 6-char room code, mark themselves ready. Game auto-starts when everyone is ready (min 4 players); host can also force-start.
2. **Role reveal** — each player sees their own role privately; everyone acknowledges before night begins.
3. **Night** — werewolves vote on a victim (private channel), seer investigates one player, witch decides whether to heal the werewolves' target and/or kill someone of her own.
4. **Mayor election** — first morning only: everyone votes for a Mayor. The Mayor's day vote counts double for the rest of the game. Re-election happens if the Mayor dies.
5. **Day discussion** (2 min timer) → **Day vote** → **Day result** (8s announcement screen everyone sees together).
6. **Win**: villagers when all werewolves are eliminated; werewolves when they equal or outnumber the rest.

Detailed rules are also available in-app at `/how-to-play`.

## Sandbox Mode & Voice-to-Text (Speech-to-Text)

### Sandbox Mode (Solo Playtesting)
Hosts can toggle **Sandbox Mode** when creating a room. When active, any empty player slots are automatically populated with simulated bots (`Bot Lyra`, `Bot Edmund`, `Bot Casimir`) when the game starts. 
- Bots automatically perform their night actions, day voting, and other gameplay decisions.
- Allows a developer or researcher to solo-playtest the entire multi-phase game loop in a single browser window.

### Voice-to-Text (Speech-to-Text)
The trust-labeling panel (`LabelPanel.tsx`) integrates a real-time speech-to-text reasoning helper. Speak your thoughts naturally, and they will be transcribed directly into the reasoning text area.
- **Model**: Powered by Deepgram's state-of-the-art **Nova-3** model for low-latency, highly accurate word-by-word streaming.
- **Language Selection**: A toggle between English (`EN`) and German (`DE`) is built directly into the UI. Explicitly selecting the language prevents phonetic translation errors (e.g., Deepgram transcribing German speech into phonetically similar but nonsensical English words).
- **Network Resilience**: Operates via a real-time WebSocket connection. If the client is behind a restrictive university or corporate firewall (or VPN) that blocks WebSockets, it automatically and gracefully falls back to a chunked **HTTP POST fallback API** (`/api/speech-to-text`) which dynamically routes the correct language header.
- **AI Silence Detection**: Automatically stops recording after 6 seconds of silence to conserve API credits and provide a hands-free UX.

## Research data

The admin dashboard (`/admin`, login at `/admin/login`) lists every game with a one-click CSV export. Each row has a `type` column:

- `chat` — public chat messages (day) and werewolf chat (night)
- `note` — private per-player notes (never broadcast)
- `night_action` — wolf kill, seer investigation, witch heal/kill

System messages, the day-result announcement, mayor election outcomes, and eliminations are all included for full reconstruction of any game session.

## Scripts

```bash
npm run dev          # tsx server.ts in dev mode
npm run build        # next build
npm run start        # production server
npm run db:push      # apply Prisma schema to the DB
npm run db:studio    # open Prisma Studio
npm run lint
```

## Changelog

See [CHANGELOG.md](./CHANGELOG.md) for a dated, user-facing summary of every change that has landed on `main`.

## Deploying to Railway

1. Create a Railway project and add the **PostgreSQL** and **Redis** plugins.
2. Point a new service at this repo. Railway will use the `Dockerfile`.
3. Set `ADMIN_SECRET` and `NEXT_PUBLIC_APP_URL` (the public domain Railway assigns) in the service's variables.
4. The container runs `prisma db push` on boot, so the schema is applied automatically.
