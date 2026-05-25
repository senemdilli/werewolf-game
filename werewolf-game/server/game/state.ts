import { redis } from '@/lib/redis'
import type {
  GameState, ClientGameState, PublicPlayer, Phase, GameMode,
  WolfArenaView, ConversationView, AdvocacyView, MayorRunoffView,
  WitchSelfHealSetting,
} from '@/types/game'
import { v4 as uuidv4 } from 'uuid'

const GAME_TTL = 60 * 60 * 24

export function createInitialState(
  roomCode: string,
  hostSocketId: string,
  hostName: string,
  gameMode: GameMode,
  witchSelfHeal: WitchSelfHealSetting,
): GameState {
  const hostId = uuidv4()
  return {
    id: uuidv4(),
    roomCode,
    gameMode,
    witchSelfHeal,
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
      wolfArena: null,
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
    conversation: null,
    advocacy: null,
    mayorRunoff: null,
    pendingMayorTiebreak: null,
    labelingBreak: null,
    labelingBreakUsed: [],
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
  const aliveWolves = alivePlayers.filter(p => p.role === 'werewolf')

  const wolfArena =
    state.gameMode === 'arena' && aliveWolves.length > 1
      ? {
          order: [...aliveWolves.map(w => w.id)].sort(() => Math.random() - 0.5),
          round: 1,
          turn: 0,
          currentVotes: {},
          history: [],
          resolved: false,
        }
      : null

  return {
    ...state,
    nightActions: {
      werewolfVotes: {},
      killTarget: null,
      seerTarget: null,
      witchHeal: null,
      witchKill: null,
      wolfArena,
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
  const wolvesActed = isWitch
    ? state.nightActions.completed.werewolves
    : undefined
  const nightKillTarget = isWitch && state.nightActions.completed.werewolves
    ? (() => {
        if (!state.nightActions.killTarget) return null
        const t = state.players.find(p => p.id === state.nightActions.killTarget)
        return t ? { id: t.id, name: t.name } : null
      })()
    : undefined

  // Arena: per-wolf view of the sequential vote
  let wolfArena: WolfArenaView | null | undefined
  if (me?.role === 'werewolf' && me.isAlive && state.phase === 'night' && state.nightActions.wolfArena) {
    const arena = state.nightActions.wolfArena
    wolfArena = {
      order: arena.order,
      round: arena.round,
      turn: arena.turn,
      currentVotes: arena.currentVotes,
      history: arena.history,
      myTurn: arena.order[arena.turn] === me.id && !arena.resolved,
      resolved: arena.resolved,
    }
  } else if (me?.role === 'werewolf' && state.phase === 'night') {
    wolfArena = null
  }

  // Conversation view (Arena): private bid value, public speaker / round / history.
  let conversation: ConversationView | null = null
  if (state.conversation && state.conversation.active) {
    const c = state.conversation
    conversation = {
      active: c.active,
      context: c.context,
      round: c.round,
      maxRounds: c.maxRounds,
      sub: c.sub,
      myBid: c.bids[playerId] ?? null,
      bidEndTime: c.bidEndTime,
      speakerId: c.speakerId,
      speakerName: c.speakerName,
      speakerEndTime: c.speakerEndTime,
      bidsSubmittedCount: Object.keys(c.bids).length,
      pendingSpeakers: c.pendingSpeakers ?? [],
      history: c.history,
    }
  }

  // Advocacy view (Arena mayor election): same view for all players.
  let advocacy: AdvocacyView | null = null
  if (state.advocacy && state.advocacy.active) {
    const a = state.advocacy
    const currentSpeakerId = a.order[a.turn] ?? null
    advocacy = {
      active: a.active,
      order: a.order,
      turn: a.turn,
      endTime: a.endTime,
      currentSpeakerId,
      myTurn: currentSpeakerId === playerId,
    }
  }

  // Mayor runoff view (Arena tied mayor election).
  let mayorRunoff: MayorRunoffView | null = null
  if (state.mayorRunoff && state.mayorRunoff.active) {
    const r = state.mayorRunoff
    mayorRunoff = {
      active: r.active,
      candidates: r.candidates,
      myVote: r.votes[playerId] ?? null,
      endTime: r.endTime,
      votesSubmitted: Object.keys(r.votes).length,
    }
  }

  // Arena day-vote tiebreak: only the mayor sees the candidate list to choose from.
  const mayorTiebreakCandidates =
    state.pendingMayorTiebreak && state.mayorId === playerId
      ? state.pendingMayorTiebreak
      : null
  const mayorTiebreakPending = !!state.pendingMayorTiebreak

  // Labeling break info — visible to everyone; the "available" flag is
  // per-player (only alive players may request).
  const BREAK_PHASES = new Set<Phase>([
    'day_discussion', 'day_vote', 'mayor_election', 'day_result',
  ])
  const breakKey = `${state.phase}:${state.round}`
  const labelingBreakUsed = state.labelingBreakUsed ?? []
  const labelingBreak = state.labelingBreak?.active
    ? { endTime: state.labelingBreak.endTime }
    : null
  const labelingBreakAvailable =
    !!me?.isAlive &&
    BREAK_PHASES.has(state.phase) &&
    !labelingBreak &&
    !labelingBreakUsed.includes(breakKey) &&
    !state.conversation?.active &&
    !state.advocacy?.active &&
    !state.mayorRunoff?.active &&
    !state.pendingMayorTiebreak

  return {
    id: state.id,
    roomCode: state.roomCode,
    gameMode: state.gameMode,
    witchSelfHeal: state.witchSelfHeal,
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
    wolfArena,
    wolvesActed,
    nightKillTarget,
    witchPotions: isWitch ? state.witchPotions : undefined,
    conversation,
    advocacy,
    mayorRunoff,
    mayorTiebreakCandidates,
    mayorTiebreakPending,
    labelingBreak,
    labelingBreakAvailable,
  }
}
