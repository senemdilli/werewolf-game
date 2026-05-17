import type { Server, Socket } from 'socket.io'
import type { ServerToClientEvents, ClientToServerEvents, Role, GameState } from '@/types/game'
import { SKIP_VOTE } from '@/types/game'
import {
  getGame, saveGame, resetNightActions,
  areNightActionsDone, areDayVotesDone, areMayorVotesDone,
  buildClientState,
} from '@/server/game/state'
import {
  assignRoles, checkWinCondition,
  resolveWerewolfKill, resolveDayVote, resolveMayorElection,
} from '@/server/game/roles'
import { prisma } from '@/lib/prisma'

type GameSocket = Socket<ClientToServerEvents, ServerToClientEvents>
type GameServer = Server<ClientToServerEvents, ServerToClientEvents>

const DAY_DISCUSSION_MS = 2 * 60 * 1000
const DAY_VOTE_MS = 60 * 1000
const MAYOR_ELECTION_MS = 60 * 1000
const DAY_RESULT_MS = 8 * 1000

const phaseTimers = new Map<string, ReturnType<typeof setTimeout>>()

function clearPhaseTimer(roomCode: string) {
  const t = phaseTimers.get(roomCode)
  if (t) { clearTimeout(t); phaseTimers.delete(roomCode) }
}

async function broadcastState(io: GameServer, roomCode: string) {
  const state = await getGame(roomCode)
  if (!state) return
  for (const p of state.players) {
    io.to(p.socketId).emit('game:state', buildClientState(state, p.id))
  }
}

// ── Phase transitions ────────────────────────────────────────────────────────

async function transitionToNight(io: GameServer, roomCode: string) {
  clearPhaseTimer(roomCode)
  let state = await getGame(roomCode)
  if (!state) return

  state.round += 1
  state = resetNightActions(state)
  state.phase = 'night'
  state.lastEliminated = null
  state.phaseEndTime = null

  for (const p of state.players) {
    if (p.role === 'werewolf') {
      io.sockets.sockets.get(p.socketId)?.join(`wolves:${roomCode}`)
    }
  }

  await saveGame(state)
  await broadcastState(io, roomCode)
  if (state.dbGameId) await persistSystem(state.dbGameId, `Night ${state.round} begins.`, 'NIGHT', state.round)
}

async function transitionToMayorElection(
  io: GameServer,
  roomCode: string,
  postPhase: 'day_discussion' | 'night'
) {
  clearPhaseTimer(roomCode)
  const state = await getGame(roomCode)
  if (!state) return

  state.phase = 'mayor_election'
  state.mayorVotes = {}
  state.postElectionPhase = postPhase
  state.phaseEndTime = Date.now() + MAYOR_ELECTION_MS

  await saveGame(state)
  if (state.dbGameId) await persistSystem(state.dbGameId, 'The village must elect a Mayor.', 'DAY', state.round)
  await broadcastState(io, roomCode)

  const timer = setTimeout(() => {
    phaseTimers.delete(roomCode)
    finalizeMayorElection(io, roomCode)
  }, MAYOR_ELECTION_MS)
  phaseTimers.set(roomCode, timer)
}

async function finalizeMayorElection(io: GameServer, roomCode: string) {
  clearPhaseTimer(roomCode)
  const state = await getGame(roomCode)
  if (!state || state.phase !== 'mayor_election') return

  const winnerId = resolveMayorElection(state.mayorVotes)

  if (winnerId) {
    state.mayorId = winnerId
    const name = state.players.find(p => p.id === winnerId)?.name ?? 'Someone'
    state.mayorElected = true
    if (state.dbGameId) await persistSystem(state.dbGameId, `${name} has been elected Mayor. Their vote counts double.`, 'DAY', state.round)
  }

  const next = state.postElectionPhase ?? 'day_discussion'
  state.postElectionPhase = null

  if (next === 'day_discussion') {
    await startDayDiscussion(io, state)
  } else {
    await saveGame(state)
    await transitionToNight(io, roomCode)
  }
}

async function startDayDiscussion(io: GameServer, state: GameState) {
  state.phase = 'day_discussion'
  state.dayVotes = { votes: {} }
  state.phaseEndTime = Date.now() + DAY_DISCUSSION_MS
  await saveGame(state)
  await broadcastState(io, state.roomCode)

  const timer = setTimeout(() => {
    phaseTimers.delete(state.roomCode)
    transitionToDayVote(io, state.roomCode)
  }, DAY_DISCUSSION_MS)
  phaseTimers.set(state.roomCode, timer)
}

async function transitionAfterNight(io: GameServer, roomCode: string) {
  clearPhaseTimer(roomCode)
  const state = await getGame(roomCode)
  if (!state) return

  const killTargetId = resolveWerewolfKill(state.nightActions.werewolfVotes)
  const healId = state.nightActions.witchHeal
  const witchKillId = state.nightActions.witchKill

  const victims: Array<{ id: string; name: string; role: Role }> = []
  let savedByWitch = false

  // Werewolf kill (blocked if witch healed)
  if (killTargetId) {
    if (healId === killTargetId) {
      savedByWitch = true
    } else {
      const victim = state.players.find(p => p.id === killTargetId)
      if (victim && victim.isAlive) {
        victim.isAlive = false
        victims.push({ id: victim.id, name: victim.name, role: victim.role as Role })
      }
    }
  }

  // Witch kill
  if (witchKillId) {
    const victim = state.players.find(p => p.id === witchKillId)
    if (victim && victim.isAlive) {
      victim.isAlive = false
      victims.push({ id: victim.id, name: victim.name, role: victim.role as Role })
    }
  }

  // Persist eliminations
  for (const v of victims) {
    if (state.dbGameId) {
      const dbP = await prisma.player.findFirst({ where: { gameId: state.dbGameId, name: v.name } })
      if (dbP) await prisma.player.update({ where: { id: dbP.id }, data: { eliminationRound: state.round, eliminationPhase: 'NIGHT' } })
    }
  }

  // Build announcement
  let systemMsg: string
  if (savedByWitch && victims.length === 0) {
    systemMsg = 'Dawn breaks. The witch saved someone from the werewolves tonight. No one was killed.'
  } else if (savedByWitch && victims.length > 0) {
    systemMsg = `Dawn breaks. The witch saved the werewolves' target, but also used her kill potion. ${victims.map(v => `${v.name} (${v.role})`).join(' and ')} ${victims.length > 1 ? 'were' : 'was'} found dead.`
  } else if (victims.length === 0) {
    systemMsg = 'Dawn breaks. No one was eliminated last night.'
  } else {
    systemMsg = `Dawn breaks. ${victims.map(v => `${v.name} (${v.role})`).join(' and ')} ${victims.length > 1 ? 'were' : 'was'} found dead.`
  }

  if (victims.length === 1) {
    state.lastEliminated = { playerId: victims[0].id, playerName: victims[0].name, role: victims[0].role }
  }

  const winner = checkWinCondition(state.players)
  if (winner) {
    state.winner = winner
    state.phase = 'game_over'
    state.phaseEndTime = null
    await saveGame(state)
    await finalizeGame(state.dbGameId!, winner, state.round)
    if (state.dbGameId) await persistSystem(state.dbGameId, systemMsg, 'DAY', state.round)
    await broadcastState(io, state.roomCode)
    return
  }

  if (state.dbGameId) await persistSystem(state.dbGameId, systemMsg, 'DAY', state.round)

  const mayorDied = victims.some(v => v.id === state.mayorId)
  if (mayorDied) state.mayorId = null

  // Determine next phase
  if (!state.mayorElected) {
    // First election ever
    await saveGame(state)
    await transitionToMayorElection(io, state.roomCode, 'day_discussion')
  } else if (mayorDied) {
    // Re-election
    await saveGame(state)
    await transitionToMayorElection(io, state.roomCode, 'day_discussion')
  } else {
    await startDayDiscussion(io, state)
  }
}

async function transitionToDayVote(io: GameServer, roomCode: string) {
  clearPhaseTimer(roomCode)
  const state = await getGame(roomCode)
  if (!state || state.phase !== 'day_discussion') return

  state.phase = 'day_vote'
  state.dayVotes = { votes: {} }
  state.phaseEndTime = Date.now() + DAY_VOTE_MS
  await saveGame(state)
  if (state.dbGameId) await persistSystem(state.dbGameId, 'Voting begins.', 'DAY', state.round)
  await broadcastState(io, roomCode)

  const timer = setTimeout(() => {
    phaseTimers.delete(roomCode)
    resolveVoteAndAdvance(io, roomCode)
  }, DAY_VOTE_MS)
  phaseTimers.set(roomCode, timer)
}

async function resolveVoteAndAdvance(io: GameServer, roomCode: string) {
  clearPhaseTimer(roomCode)
  const state = await getGame(roomCode)
  if (!state || state.phase !== 'day_vote') return

  const { outcome, eliminatedId } = resolveDayVote(state.dayVotes.votes, state.mayorId)
  let systemMsg = ''
  state.lastEliminated = null
  state.dayVoteOutcome = outcome

  if (outcome === 'eliminated' && eliminatedId) {
    const victim = state.players.find(p => p.id === eliminatedId)
    if (victim) {
      victim.isAlive = false
      state.lastEliminated = { playerId: victim.id, playerName: victim.name, role: victim.role as Role }
      systemMsg = `The village voted. ${victim.name} (${victim.role}) has been eliminated.`
      if (state.dbGameId) {
        const dbP = await prisma.player.findFirst({ where: { gameId: state.dbGameId, name: victim.name } })
        if (dbP) await prisma.player.update({ where: { id: dbP.id }, data: { eliminationRound: state.round, eliminationPhase: 'DAY' } })
      }
    }
  } else if (outcome === 'skipped') {
    systemMsg = 'The village voted to skip. No one was eliminated.'
  } else {
    systemMsg = 'The vote ended in a tie. No one was eliminated.'
  }

  const winner = checkWinCondition(state.players)
  if (winner) {
    state.winner = winner
    state.phase = 'game_over'
    state.phaseEndTime = null
    await saveGame(state)
    await finalizeGame(state.dbGameId!, winner, state.round)
    if (state.dbGameId) await persistSystem(state.dbGameId, systemMsg, 'DAY', state.round)
    await broadcastState(io, roomCode)
    return
  }

  if (state.dbGameId) await persistSystem(state.dbGameId, systemMsg, 'DAY', state.round)

  state.phase = 'day_result'
  state.phaseEndTime = Date.now() + DAY_RESULT_MS
  await saveGame(state)
  await broadcastState(io, roomCode)

  const timer = setTimeout(() => {
    phaseTimers.delete(roomCode)
    transitionAfterDayResult(io, roomCode)
  }, DAY_RESULT_MS)
  phaseTimers.set(roomCode, timer)
}

async function transitionAfterDayResult(io: GameServer, roomCode: string) {
  clearPhaseTimer(roomCode)
  const state = await getGame(roomCode)
  if (!state || state.phase !== 'day_result') return

  const mayorDied = state.lastEliminated?.playerId === state.mayorId
  if (mayorDied) state.mayorId = null

  state.dayVoteOutcome = null
  state.phaseEndTime = null

  if (mayorDied) {
    await saveGame(state)
    await transitionToMayorElection(io, roomCode, 'night')
  } else {
    await saveGame(state)
    await transitionToNight(io, roomCode)
  }
}

// ── Helpers ──────────────────────────────────────────────────────────────────

async function persistSystem(gameId: string, content: string, phase: 'DAY' | 'NIGHT', round: number) {
  try {
    await prisma.message.create({ data: { gameId, playerName: 'System', content, phase, round, isSystem: true } })
  } catch (err) { console.error('[persistSystem]', err) }
}

async function finalizeGame(gameId: string, winner: string, totalRounds: number) {
  try {
    await prisma.game.update({
      where: { id: gameId },
      data: { status: 'FINISHED', winner: winner === 'villagers' ? 'VILLAGERS' : 'WEREWOLVES', totalRounds, endedAt: new Date() },
    })
  } catch (err) { console.error('[finalizeGame]', err) }
}

async function getDbPlayerId(gameId: string, name: string): Promise<string> {
  const p = await prisma.player.findFirst({ where: { gameId, name } })
  return p?.id ?? ''
}

// ── Handler registration ──────────────────────────────────────────────────────

export async function startGame(io: GameServer, roomCode: string): Promise<void> {
  const state = await getGame(roomCode)
  if (!state || state.phase !== 'lobby' || state.players.length < 4) return

  state.players = assignRoles(state.players)
  state.phase = 'role_reveal'

  const dbGame = await prisma.game.create({
    data: {
      roomCode,
      status: 'IN_PROGRESS',
      playerCount: state.players.length,
      startedAt: new Date(),
      players: {
        create: state.players.map(p => ({
          name: p.name,
          role: p.role!.toUpperCase() as import('@prisma/client').$Enums.Role,
        })),
      },
    },
  })
  state.dbGameId = dbGame.id

  for (const p of state.players) {
    if (p.role === 'werewolf') io.sockets.sockets.get(p.socketId)?.join(`wolves:${roomCode}`)
  }

  await saveGame(state)
  await broadcastState(io, roomCode)
}

export function registerGameHandlers(io: GameServer, socket: GameSocket) {

  socket.on('game:start', async (cb) => {
    try {
      const { playerId, roomCode } = socket.data
      const state = await getGame(roomCode)
      if (!state) return cb({ success: false, error: 'Room not found' })
      const player = state.players.find(p => p.id === playerId)
      if (!player?.isHost) return cb({ success: false, error: 'Only the host can start' })
      if (state.players.length < 4) return cb({ success: false, error: 'Need at least 4 players' })
      if (state.phase !== 'lobby') return cb({ success: false, error: 'Already started' })

      await startGame(io, roomCode)
      cb({ success: true })
    } catch (err) {
      console.error('[game:start]', err)
      cb({ success: false, error: 'Failed to start game' })
    }
  })

  socket.on('game:acknowledge_role', async () => {
    try {
      const { playerId, roomCode } = socket.data
      const state = await getGame(roomCode)
      if (!state || state.phase !== 'role_reveal') return

      const player = state.players.find(p => p.id === playerId)
      if (player) player.roleAcknowledged = true

      if (state.players.every(p => p.roleAcknowledged)) {
        await saveGame(state)
        await transitionToNight(io, roomCode)
      } else {
        await saveGame(state)
        await broadcastState(io, roomCode)
      }
    } catch (err) { console.error('[game:acknowledge_role]', err) }
  })

  socket.on('night:werewolf_vote', async (targetId) => {
    try {
      const { playerId, roomCode } = socket.data
      const state = await getGame(roomCode)
      if (!state || state.phase !== 'night') return

      const voter = state.players.find(p => p.id === playerId)
      if (!voter || voter.role !== 'werewolf' || !voter.isAlive) return

      const target = state.players.find(p => p.id === targetId && p.isAlive && p.role !== 'werewolf')
      if (!target) return

      state.nightActions.werewolfVotes[playerId] = targetId

      const aliveWolves = state.players.filter(p => p.role === 'werewolf' && p.isAlive)
      if (aliveWolves.every(w => !!state.nightActions.werewolfVotes[w.id])) {
        state.nightActions.completed.werewolves = true
        // Resolve kill target now so witch can see it
        state.nightActions.killTarget = resolveWerewolfKill(state.nightActions.werewolfVotes)
      }

      if (state.dbGameId) {
        await prisma.nightAction.upsert({
          where: { id: `${state.dbGameId}-${playerId}-${state.round}-kill` },
          create: { id: `${state.dbGameId}-${playerId}-${state.round}-kill`, gameId: state.dbGameId, playerId: await getDbPlayerId(state.dbGameId, voter.name), actionType: 'KILL', targetPlayerId: await getDbPlayerId(state.dbGameId, target.name), round: state.round },
          update: { targetPlayerId: await getDbPlayerId(state.dbGameId, target.name) },
        }).catch(() => {})
      }

      await saveGame(state)
      if (areNightActionsDone(state)) await transitionAfterNight(io, roomCode)
      else await broadcastState(io, roomCode)
    } catch (err) { console.error('[night:werewolf_vote]', err) }
  })

  socket.on('night:seer_investigate', async (targetId) => {
    try {
      const { playerId, roomCode } = socket.data
      const state = await getGame(roomCode)
      if (!state || state.phase !== 'night') return

      const seer = state.players.find(p => p.id === playerId)
      if (!seer || seer.role !== 'seer' || !seer.isAlive) return

      const target = state.players.find(p => p.id === targetId && p.isAlive)
      if (!target) return

      state.nightActions.seerTarget = targetId
      state.nightActions.completed.seer = true

      if (state.dbGameId) {
        await prisma.nightAction.create({
          data: { gameId: state.dbGameId, playerId: await getDbPlayerId(state.dbGameId, seer.name), actionType: 'INVESTIGATE', targetPlayerId: await getDbPlayerId(state.dbGameId, target.name), round: state.round },
        }).catch(() => {})
      }

      // Seer sees faction only (not exact role)
      socket.emit('seer:result', { targetName: target.name, isWerewolf: target.role === 'werewolf' })

      await saveGame(state)
      if (areNightActionsDone(state)) await transitionAfterNight(io, roomCode)
      else await broadcastState(io, roomCode)
    } catch (err) { console.error('[night:seer_investigate]', err) }
  })

  socket.on('night:witch_action', async ({ heal, kill }) => {
    try {
      const { playerId, roomCode } = socket.data
      const state = await getGame(roomCode)
      if (!state || state.phase !== 'night') return

      const witch = state.players.find(p => p.id === playerId)
      if (!witch || witch.role !== 'witch' || !witch.isAlive) return

      // Witch can only act after wolves have decided their target
      const aliveWolves = state.players.filter(p => p.role === 'werewolf' && p.isAlive)
      const wolvesActed = aliveWolves.every(w => !!state.nightActions.werewolfVotes[w.id])
      if (!wolvesActed) return

      if (heal && state.witchPotions.heal) {
        const target = state.players.find(p => p.id === heal && p.isAlive)
        if (target) {
          state.nightActions.witchHeal = heal
          state.witchPotions.heal = false
          if (state.dbGameId) {
            await prisma.nightAction.create({
              data: { gameId: state.dbGameId, playerId: await getDbPlayerId(state.dbGameId, witch.name), actionType: 'HEAL', targetPlayerId: await getDbPlayerId(state.dbGameId, target.name), round: state.round },
            }).catch(() => {})
          }
        }
      }

      if (kill && state.witchPotions.kill) {
        const target = state.players.find(p => p.id === kill && p.isAlive)
        if (target) {
          state.nightActions.witchKill = kill
          state.witchPotions.kill = false
          if (state.dbGameId) {
            await prisma.nightAction.create({
              data: { gameId: state.dbGameId, playerId: await getDbPlayerId(state.dbGameId, witch.name), actionType: 'WITCH_KILL', targetPlayerId: await getDbPlayerId(state.dbGameId, target.name), round: state.round },
            }).catch(() => {})
          }
        }
      }

      state.nightActions.completed.witch = true
      await saveGame(state)
      if (areNightActionsDone(state)) await transitionAfterNight(io, roomCode)
      else await broadcastState(io, roomCode)
    } catch (err) { console.error('[night:witch_action]', err) }
  })

  socket.on('day:vote', async (targetId) => {
    try {
      const { playerId, roomCode } = socket.data
      const state = await getGame(roomCode)
      if (!state || state.phase !== 'day_vote') return

      const voter = state.players.find(p => p.id === playerId)
      if (!voter || !voter.isAlive) return

      if (targetId !== SKIP_VOTE) {
        const target = state.players.find(p => p.id === targetId && p.isAlive && p.id !== playerId)
        if (!target) return
      }

      state.dayVotes.votes[playerId] = targetId
      await saveGame(state)
      if (areDayVotesDone(state)) await resolveVoteAndAdvance(io, roomCode)
      else await broadcastState(io, roomCode)
    } catch (err) { console.error('[day:vote]', err) }
  })

  socket.on('mayor:vote', async (targetId) => {
    try {
      const { playerId, roomCode } = socket.data
      const state = await getGame(roomCode)
      if (!state || state.phase !== 'mayor_election') return

      const voter = state.players.find(p => p.id === playerId)
      if (!voter || !voter.isAlive) return

      const target = state.players.find(p => p.id === targetId && p.isAlive && p.id !== playerId)
      if (!target) return

      state.mayorVotes[playerId] = targetId
      await saveGame(state)
      if (areMayorVotesDone(state)) await finalizeMayorElection(io, roomCode)
      else await broadcastState(io, roomCode)
    } catch (err) { console.error('[mayor:vote]', err) }
  })

  socket.on('phase:advance', async () => {
    try {
      const { playerId, roomCode } = socket.data
      const state = await getGame(roomCode)
      if (!state) return
      const player = state.players.find(p => p.id === playerId)
      if (!player?.isHost) return

      if (state.phase === 'night') await transitionAfterNight(io, roomCode)
      else if (state.phase === 'mayor_election') await finalizeMayorElection(io, roomCode)
      else if (state.phase === 'day_discussion') await transitionToDayVote(io, roomCode)
      else if (state.phase === 'day_vote') await resolveVoteAndAdvance(io, roomCode)
      else if (state.phase === 'day_result') await transitionAfterDayResult(io, roomCode)
    } catch (err) { console.error('[phase:advance]', err) }
  })
}
