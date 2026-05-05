import type { Server, Socket } from 'socket.io'
import type { ServerToClientEvents, ClientToServerEvents, Role } from '@/types/game'
import {
  getGame,
  saveGame,
  resetNightActions,
  areNightActionsDone,
  areDayVotesDone,
  buildClientState,
} from '@/server/game/state'
import {
  assignRoles,
  checkWinCondition,
  resolveNightKill,
  resolveDayVote,
} from '@/server/game/roles'
import { prisma } from '@/lib/prisma'

type GameSocket = Socket<ClientToServerEvents, ServerToClientEvents>
type GameServer = Server<ClientToServerEvents, ServerToClientEvents>

const DAY_DISCUSSION_MS = 2 * 60 * 1000 // 2 minutes

const phaseTimers = new Map<string, ReturnType<typeof setTimeout>>()

function clearPhaseTimer(roomCode: string) {
  const t = phaseTimers.get(roomCode)
  if (t) { clearTimeout(t); phaseTimers.delete(roomCode) }
}

async function broadcastState(io: GameServer, roomCode: string) {
  const state = await getGame(roomCode)
  if (!state) return
  for (const player of state.players) {
    io.to(player.socketId).emit('game:state', buildClientState(state, player.id))
  }
}

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
      const wSocket = io.sockets.sockets.get(p.socketId)
      wSocket?.join(`wolves:${roomCode}`)
    }
  }

  await saveGame(state)
  await broadcastState(io, roomCode)
  await persistSystemMessage(state.dbGameId!, `Night ${state.round} begins. The village sleeps…`, 'NIGHT', state.round)
}

async function transitionToDayDiscussion(io: GameServer, roomCode: string) {
  clearPhaseTimer(roomCode)
  let state = await getGame(roomCode)
  if (!state) return

  const { killTargetId, savedByDoctor } = resolveNightKill(
    state.nightActions.werewolfVotes,
    state.nightActions.doctorTarget
  )

  let systemMsg = ''

  if (killTargetId) {
    const victim = state.players.find(p => p.id === killTargetId)
    if (victim) {
      victim.isAlive = false
      state.lastEliminated = { playerId: victim.id, playerName: victim.name, role: victim.role as Role }
      systemMsg = `Dawn breaks. ${victim.name} was found dead. They were a ${victim.role}.`

      if (state.dbGameId) {
        const dbPlayer = await prisma.player.findFirst({ where: { gameId: state.dbGameId, name: victim.name } })
        if (dbPlayer) {
          await prisma.player.update({
            where: { id: dbPlayer.id },
            data: { eliminationRound: state.round, eliminationPhase: 'NIGHT' },
          })
        }
      }
    }
  } else if (savedByDoctor) {
    systemMsg = 'Dawn breaks. The doctor saved someone tonight. No one was eliminated.'
  } else {
    systemMsg = 'Dawn breaks. No one was eliminated last night.'
  }

  const winner = checkWinCondition(state.players)
  if (winner) {
    state.winner = winner
    state.phase = 'game_over'
    state.phaseEndTime = null
    await saveGame(state)
    await finalizeGame(state.dbGameId!, winner, state.round)
    if (systemMsg && state.dbGameId) await persistSystemMessage(state.dbGameId, systemMsg, 'DAY', state.round)
    await broadcastState(io, roomCode)
    return
  }

  const endTime = Date.now() + DAY_DISCUSSION_MS
  state.phase = 'day_discussion'
  state.dayVotes = { votes: {} }
  state.phaseEndTime = endTime
  await saveGame(state)
  if (systemMsg && state.dbGameId) await persistSystemMessage(state.dbGameId, systemMsg, 'DAY', state.round)
  await broadcastState(io, roomCode)

  // Auto-advance to vote after timer
  const timer = setTimeout(() => {
    phaseTimers.delete(roomCode)
    transitionToDayVote(io, roomCode)
  }, DAY_DISCUSSION_MS)
  phaseTimers.set(roomCode, timer)
}

async function transitionToDayVote(io: GameServer, roomCode: string) {
  clearPhaseTimer(roomCode)
  const state = await getGame(roomCode)
  if (!state || state.phase !== 'day_discussion') return

  state.phase = 'day_vote'
  state.dayVotes = { votes: {} }
  state.phaseEndTime = null
  await saveGame(state)
  if (state.dbGameId) await persistSystemMessage(state.dbGameId, 'Voting begins. Cast your vote to eliminate a suspect.', 'DAY', state.round)
  await broadcastState(io, roomCode)
}

async function resolveVoteAndAdvance(io: GameServer, roomCode: string) {
  clearPhaseTimer(roomCode)
  const state = await getGame(roomCode)
  if (!state) return

  const eliminatedId = resolveDayVote(state.dayVotes.votes, state.mayorId)
  let systemMsg = ''

  if (eliminatedId) {
    const victim = state.players.find(p => p.id === eliminatedId)
    if (victim) {
      victim.isAlive = false
      state.lastEliminated = { playerId: victim.id, playerName: victim.name, role: victim.role as Role }
      systemMsg = `The village voted. ${victim.name} has been eliminated. They were a ${victim.role}.`

      if (state.dbGameId) {
        const dbPlayer = await prisma.player.findFirst({ where: { gameId: state.dbGameId, name: victim.name } })
        if (dbPlayer) {
          await prisma.player.update({
            where: { id: dbPlayer.id },
            data: { eliminationRound: state.round, eliminationPhase: 'DAY' },
          })
        }
      }
    }
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
    if (systemMsg && state.dbGameId) await persistSystemMessage(state.dbGameId, systemMsg, 'DAY', state.round)
    await broadcastState(io, roomCode)
    return
  }

  if (systemMsg && state.dbGameId) await persistSystemMessage(state.dbGameId, systemMsg, 'DAY', state.round)
  await saveGame(state)
  await transitionToNight(io, roomCode)
}

async function persistSystemMessage(gameId: string, content: string, phase: 'DAY' | 'NIGHT', round: number) {
  try {
    await prisma.message.create({
      data: { gameId, playerName: 'System', content, phase: phase as 'DAY' | 'NIGHT', round, isSystem: true },
    })
  } catch (err) {
    console.error('[persistSystemMessage]', err)
  }
}

async function finalizeGame(gameId: string, winner: string, totalRounds: number) {
  try {
    await prisma.game.update({
      where: { id: gameId },
      data: {
        status: 'FINISHED',
        winner: winner === 'villagers' ? 'VILLAGERS' : 'WEREWOLVES',
        totalRounds,
        endedAt: new Date(),
      },
    })
  } catch (err) {
    console.error('[finalizeGame]', err)
  }
}

export function registerGameHandlers(io: GameServer, socket: GameSocket) {
  socket.on('game:start', async (cb) => {
    try {
      const { playerId, roomCode } = socket.data
      const state = await getGame(roomCode)
      if (!state) return cb({ success: false, error: 'Room not found' })
      if (state.hostId !== playerId) return cb({ success: false, error: 'Only the host can start the game' })
      if (state.players.length < 4) return cb({ success: false, error: 'Need at least 4 players' })
      if (state.phase !== 'lobby') return cb({ success: false, error: 'Game already started' })

      const { players: withRoles, mayorId } = assignRoles(state.players)
      state.players = withRoles
      state.mayorId = mayorId
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
        if (p.role === 'werewolf') {
          const wSocket = io.sockets.sockets.get(p.socketId)
          wSocket?.join(`wolves:${roomCode}`)
        }
      }

      await saveGame(state)
      await broadcastState(io, roomCode)
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
    } catch (err) {
      console.error('[game:acknowledge_role]', err)
    }
  })

  socket.on('night:werewolf_vote', async (targetId) => {
    try {
      const { playerId, roomCode } = socket.data
      const state = await getGame(roomCode)
      if (!state || state.phase !== 'night') return

      const voter = state.players.find(p => p.id === playerId)
      if (!voter || voter.role !== 'werewolf' || !voter.isAlive) return

      const target = state.players.find(p => p.id === targetId)
      if (!target || !target.isAlive || target.role === 'werewolf') return

      state.nightActions.werewolfVotes[playerId] = targetId

      const aliveWolves = state.players.filter(p => p.role === 'werewolf' && p.isAlive)
      if (aliveWolves.every(w => !!state.nightActions.werewolfVotes[w.id])) {
        state.nightActions.completed.werewolves = true
      }

      if (state.dbGameId) {
        await prisma.nightAction.upsert({
          where: { id: `${state.dbGameId}-${playerId}-${state.round}-kill` },
          create: {
            id: `${state.dbGameId}-${playerId}-${state.round}-kill`,
            gameId: state.dbGameId,
            playerId: await getDbPlayerId(state.dbGameId, voter.name),
            actionType: 'KILL',
            targetPlayerId: await getDbPlayerId(state.dbGameId, target.name),
            round: state.round,
          },
          update: { targetPlayerId: await getDbPlayerId(state.dbGameId, target.name) },
        }).catch(() => {})
      }

      await saveGame(state)
      if (areNightActionsDone(state)) {
        await transitionToDayDiscussion(io, roomCode)
      } else {
        await broadcastState(io, roomCode)
      }
    } catch (err) {
      console.error('[night:werewolf_vote]', err)
    }
  })

  socket.on('night:seer_investigate', async (targetId) => {
    try {
      const { playerId, roomCode } = socket.data
      const state = await getGame(roomCode)
      if (!state || state.phase !== 'night') return

      const seer = state.players.find(p => p.id === playerId)
      if (!seer || seer.role !== 'seer' || !seer.isAlive) return

      const target = state.players.find(p => p.id === targetId)
      if (!target || !target.isAlive) return

      state.nightActions.seerTarget = targetId
      state.nightActions.completed.seer = true

      if (state.dbGameId) {
        await prisma.nightAction.create({
          data: {
            gameId: state.dbGameId,
            playerId: await getDbPlayerId(state.dbGameId, seer.name),
            actionType: 'INVESTIGATE',
            targetPlayerId: await getDbPlayerId(state.dbGameId, target.name),
            round: state.round,
          },
        }).catch(() => {})
      }

      socket.emit('seer:result', { targetName: target.name, isWerewolf: target.role === 'werewolf' })

      await saveGame(state)
      if (areNightActionsDone(state)) {
        await transitionToDayDiscussion(io, roomCode)
      } else {
        await broadcastState(io, roomCode)
      }
    } catch (err) {
      console.error('[night:seer_investigate]', err)
    }
  })

  socket.on('night:doctor_save', async (targetId) => {
    try {
      const { playerId, roomCode } = socket.data
      const state = await getGame(roomCode)
      if (!state || state.phase !== 'night') return

      const doctor = state.players.find(p => p.id === playerId)
      if (!doctor || doctor.role !== 'doctor' || !doctor.isAlive) return

      const target = state.players.find(p => p.id === targetId)
      if (!target || !target.isAlive) return

      state.nightActions.doctorTarget = targetId
      state.nightActions.completed.doctor = true

      if (state.dbGameId) {
        await prisma.nightAction.create({
          data: {
            gameId: state.dbGameId,
            playerId: await getDbPlayerId(state.dbGameId, doctor.name),
            actionType: 'SAVE',
            targetPlayerId: await getDbPlayerId(state.dbGameId, target.name),
            round: state.round,
          },
        }).catch(() => {})
      }

      await saveGame(state)
      if (areNightActionsDone(state)) {
        await transitionToDayDiscussion(io, roomCode)
      } else {
        await broadcastState(io, roomCode)
      }
    } catch (err) {
      console.error('[night:doctor_save]', err)
    }
  })

  socket.on('day:vote', async (targetId) => {
    try {
      const { playerId, roomCode } = socket.data
      const state = await getGame(roomCode)
      if (!state || state.phase !== 'day_vote') return

      const voter = state.players.find(p => p.id === playerId)
      if (!voter || !voter.isAlive) return

      const target = state.players.find(p => p.id === targetId)
      if (!target || !target.isAlive || target.id === playerId) return

      // Allow vote changes — simply overwrite
      state.dayVotes.votes[playerId] = targetId
      await saveGame(state)

      if (areDayVotesDone(state)) {
        await resolveVoteAndAdvance(io, roomCode)
      } else {
        await broadcastState(io, roomCode)
      }
    } catch (err) {
      console.error('[day:vote]', err)
    }
  })

  socket.on('phase:advance', async () => {
    try {
      const { playerId, roomCode } = socket.data
      const state = await getGame(roomCode)
      if (!state || state.hostId !== playerId) return

      if (state.phase === 'night') await transitionToDayDiscussion(io, roomCode)
      else if (state.phase === 'day_discussion') await transitionToDayVote(io, roomCode)
      else if (state.phase === 'day_vote') await resolveVoteAndAdvance(io, roomCode)
    } catch (err) {
      console.error('[phase:advance]', err)
    }
  })
}

async function getDbPlayerId(gameId: string, name: string): Promise<string> {
  const player = await prisma.player.findFirst({ where: { gameId, name } })
  return player?.id ?? ''
}
