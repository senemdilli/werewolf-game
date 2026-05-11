import { redis } from '@/lib/redis'
import type { GameState, Player, ClientGameState, PublicPlayer, Phase } from '@/types/game'
import { v4 as uuidv4 } from 'uuid'

const GAME_TTL = 60 * 60 * 24

export function createInitialState(roomCode: string, hostSocketId: string, hostName: string): GameState {
  const hostId = uuidv4()
  return {
    id: uuidv4(),
    roomCode,
    phase: 'lobby',
    round: 0,
    players: [{
      id: hostId,
      name: hostName,
      role: null,
      isAlive: true,
      socketId: hostSocketId,
      isHost: true,
      roleAcknowledged: false,
      isReady: false,
    }],
    nightActions: {
      werewolfVotes: {},
      killTarget: null,
      seerTarget: null,
      witchHeal: null,
      witchKill: null,
      completed: { werewolves: false, seer: false, witch: false },
    },
    dayVotes: { votes: {} },
    mayorVotes: {},
    mayorId: null,
    mayorElected: false,
    postElectionPhase: null,
    witchPotions: { heal: true, kill: true },
    lastEliminated: null,
    dayVoteOutcome: null,
    winner: null,
    hostId,
    phaseEndTime: null,
    dbGameId: null,
  }
}

export async function getGame(roomCode: string): Promise<GameState | null> {
  const raw = await redis.get(`game:${roomCode}`)
  if (!raw) return null
  return JSON.parse(raw) as GameState
}

export async function saveGame(state: GameState): Promise<void> {
  await redis.setex(`game:${state.roomCode}`, GAME_TTL, JSON.stringify(state))
}

export async function deleteGame(roomCode: string): Promise<void> {
  await redis.del(`game:${roomCode}`)
}

export function resetNightActions(state: GameState): GameState {
  const alivePlayers = state.players.filter(p => p.isAlive)
  const hasSeer = alivePlayers.some(p => p.role === 'seer')
  const hasWitch = alivePlayers.some(p => p.role === 'witch')

  return {
    ...state,
    nightActions: {
      werewolfVotes: {},
      killTarget: null,
      seerTarget: null,
      witchHeal: null,
      witchKill: null,
      completed: {
        werewolves: false,
        seer: !hasSeer,
        witch: !hasWitch,
      },
    },
  }
}

export function areNightActionsDone(state: GameState): boolean {
  const alivePlayers = state.players.filter(p => p.isAlive)
  const aliveWolves = alivePlayers.filter(p => p.role === 'werewolf')
  const wolvesVoted = aliveWolves.every(w => !!state.nightActions.werewolfVotes[w.id])
  return wolvesVoted && state.nightActions.completed.seer && state.nightActions.completed.witch
}

export function areDayVotesDone(state: GameState): boolean {
  return state.players.filter(p => p.isAlive).every(p => !!state.dayVotes.votes[p.id])
}

export function areMayorVotesDone(state: GameState): boolean {
  return state.players.filter(p => p.isAlive).every(p => !!state.mayorVotes[p.id])
}

export function buildClientState(state: GameState, playerId: string): ClientGameState {
  const me = state.players.find(p => p.id === playerId)

  const players: PublicPlayer[] = state.players.map(p => {
    const revealRole =
      state.phase === 'game_over' ||
      !p.isAlive ||
      p.id === playerId ||
      (me?.role === 'werewolf' && p.role === 'werewolf')

    return {
      id: p.id,
      name: p.name,
      isAlive: p.isAlive,
      isHost: p.isHost,
      role: revealRole ? (p.role ?? undefined) : undefined,
      hasVoted: p.id in state.dayVotes.votes,
      isMayor: p.id === state.mayorId,
      isReady: p.isReady,
    }
  })

  const werewolfTeammates =
    me?.role === 'werewolf'
      ? state.players.filter(p => p.role === 'werewolf' && p.id !== playerId).map(p => p.id)
      : undefined

  let nightActionsCompleted = true
  if (state.phase === 'night' && me?.isAlive) {
    if (me.role === 'werewolf') nightActionsCompleted = !!state.nightActions.werewolfVotes[me.id]
    else if (me.role === 'seer') nightActionsCompleted = state.nightActions.completed.seer
    else if (me.role === 'witch') nightActionsCompleted = state.nightActions.completed.witch
  }

  const isWitch = me?.role === 'witch' && me.isAlive
  const nightKillTarget = isWitch && state.nightActions.killTarget
    ? (() => {
        const t = state.players.find(p => p.id === state.nightActions.killTarget)
        return t ? { id: t.id, name: t.name } : null
      })()
    : undefined

  return {
    id: state.id,
    roomCode: state.roomCode,
    phase: state.phase as Phase,
    round: state.round,
    players,
    myRole: me?.role ?? null,
    myId: playerId,
    winner: state.winner,
    lastEliminated: state.lastEliminated,
    dayVoteOutcome: state.dayVoteOutcome,
    werewolfTeammates,
    nightActionsCompleted,
    dayVotes: state.dayVotes.votes,
    mayorVotes: state.mayorVotes,
    mayorId: state.mayorId,
    aliveWerewolvesVoted:
      me?.role === 'werewolf' ? Object.keys(state.nightActions.werewolfVotes) : undefined,
    phaseEndTime: state.phaseEndTime,
    nightKillTarget,
    witchPotions: isWitch ? state.witchPotions : undefined,
  }
}
