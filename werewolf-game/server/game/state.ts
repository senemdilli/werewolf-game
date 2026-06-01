import { redis } from '@/lib/redis'
import type {
  GameState, ClientGameState, PublicPlayer, Phase, GameMode,
  WolfArenaView, ConversationView, AdvocacyView, MayorRunoffView,
  WitchSelfHealSetting,
} from '@/types/game'
import { v4 as uuidv4 } from 'uuid'
import { resolveWerewolfKill } from '@/server/game/roles'

const GAME_TTL = 60 * 60 * 24

export function createInitialState(
  roomCode: string,
  hostSocketId: string,
  hostName: string,
  gameMode: GameMode,
  witchSelfHeal: WitchSelfHealSetting,
  speakDuration: number = 60,
  bidDuration: number = 30,
  isSandbox: boolean = false,
): GameState {
  const hostId = uuidv4()
  return {
    id: uuidv4(),
    roomCode,
    gameMode,
    witchSelfHeal,
    speakDuration,
    bidDuration,
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
    labelCheckpoint: null,
    labelDecisions: {},
    isSandbox,
  }
}

export async function getGame(roomCode: string): Promise<GameState | null> {
  const raw = await redis.get(`game:${roomCode}`)
  if (!raw) return null
  return JSON.parse(raw) as GameState
}

export async function saveGame(state: GameState): Promise<void> {
  autoSimulateBotActions(state)
  await redis.setex(`game:${state.roomCode}`, GAME_TTL, JSON.stringify(state))
}

function autoSimulateBotActions(state: GameState) {
  if (!state.isSandbox) return

  const alivePlayers = state.players.filter(p => p.isAlive)
  const bots = alivePlayers.filter(p => p.isBot)

  if (bots.length === 0) return

  // 1. Role reveal auto-acknowledgement
  if (state.phase === 'role_reveal') {
    for (const b of bots) {
      b.roleAcknowledged = true
    }
  }

  // 2. Night phase actions
  else if (state.phase === 'night') {
    const aliveWolves = alivePlayers.filter(p => p.role === 'werewolf')
    const botWolves = bots.filter(p => p.role === 'werewolf')
    
    // Auto-submit werewolf bot votes
    for (const w of botWolves) {
      if (!state.nightActions.werewolfVotes[w.id]) {
        const targets = alivePlayers.filter(p => p.role !== 'werewolf')
        if (targets.length > 0) {
          const target = targets[Math.floor(Math.random() * targets.length)]
          state.nightActions.werewolfVotes[w.id] = target.id
        } else {
          state.nightActions.werewolfVotes[w.id] = 'nobody'
        }
      }
    }

    // If all wolves voted, resolve werewolf actions
    if (aliveWolves.every(w => !!state.nightActions.werewolfVotes[w.id])) {
      state.nightActions.completed.werewolves = true
      if (!state.nightActions.killTarget) {
        state.nightActions.killTarget = resolveWerewolfKill(state.nightActions.werewolfVotes)
      }
    }

    // Seer bot action
    const botSeers = bots.filter(p => p.role === 'seer')
    for (const s of botSeers) {
      if (!state.nightActions.seerTarget) {
        const targets = alivePlayers.filter(p => p.id !== s.id)
        if (targets.length > 0) {
          const target = targets[Math.floor(Math.random() * targets.length)]
          state.nightActions.seerTarget = target.id
        }
        state.nightActions.completed.seer = true
      }
    }

    // Witch bot action (only after wolves acted!)
    if (state.nightActions.completed.werewolves) {
      const botWitches = bots.filter(p => p.role === 'witch')
      for (const w of botWitches) {
        if (!state.nightActions.completed.witch) {
          // Heal potion
          if (state.nightActions.killTarget && state.witchPotions.heal) {
            const isSelf = state.nightActions.killTarget === w.id
            const canSelfHeal = !isSelf || state.witchSelfHeal === 'always' || (state.witchSelfHeal === 'first_round' && state.round === 1)
            
            if (canSelfHeal && Math.random() > 0.3) {
              state.nightActions.witchHeal = state.nightActions.killTarget
              state.witchPotions.heal = false
            }
          }
          
          // Kill potion
          if (!state.nightActions.witchHeal && state.witchPotions.kill && Math.random() > 0.8) {
            const targets = alivePlayers.filter(p => p.id !== w.id)
            if (targets.length > 0) {
              const target = targets[Math.floor(Math.random() * targets.length)]
              state.nightActions.witchKill = target.id
              state.witchPotions.kill = false
            }
          }
          
          state.nightActions.completed.witch = true
        }
      }
    }
  }

  // 3. Mayor election / Bidding / Advocacy
  else if (state.phase === 'mayor_election' || state.phase === 'day_discussion') {
    // Arena bids
    if (state.conversation && state.conversation.active && state.conversation.sub === 'bid') {
      for (const b of bots) {
        if (state.conversation.bids[b.id] === undefined) {
          state.conversation.bids[b.id] = Math.floor(Math.random() * 5) + 1
        }
      }
    }
    
    // Mayor votes
    if (state.phase === 'mayor_election' && !state.conversation?.active && !state.mayorRunoff?.active) {
      for (const b of bots) {
        if (!state.mayorVotes[b.id]) {
          const targets = alivePlayers
          const target = targets[Math.floor(Math.random() * targets.length)]
          state.mayorVotes[b.id] = target.id
        }
      }
    }

    // Runoff votes
    if (state.mayorRunoff && state.mayorRunoff.active) {
      for (const b of bots) {
        if (state.mayorRunoff.votes[b.id] === undefined) {
          const candidates = state.mayorRunoff.candidates
          const target = candidates[Math.floor(Math.random() * candidates.length)]
          state.mayorRunoff.votes[b.id] = target
        }
      }
    }
  }

  // 4. Day vote
  else if (state.phase === 'day_vote') {
    for (const b of bots) {
      if (!state.dayVotes.votes[b.id]) {
        if (Math.random() > 0.2) {
          const targets = alivePlayers.filter(p => p.id !== b.id)
          if (targets.length > 0) {
            const target = targets[Math.floor(Math.random() * targets.length)]
            state.dayVotes.votes[b.id] = target.id
          } else {
            state.dayVotes.votes[b.id] = 'skip'
          }
        } else {
          state.dayVotes.votes[b.id] = 'skip'
        }
      }
    }
  }

  // 5. Auto-skip trust-labeling checkpoints for bots
  if (state.labelCheckpoint) {
    for (const b of bots) {
      state.labelDecisions[b.id] = true
    }
  }
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
      isBot: p.isBot,
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

  // Labeling checkpoint info — exposed to all clients. Per-player decision
  // tracked for UI gating; counts surface to the "X of N ready" chip.
  const labelCheckpoint = state.labelCheckpoint
  const aliveIds = state.players.filter(p => p.isAlive).map(p => p.id)
  const labelDecidedTotal = aliveIds.length
  const labelDecidedCount = labelCheckpoint
    ? aliveIds.filter(id => state.labelDecisions[id]).length
    : 0
  const labelMeDecided = !!(labelCheckpoint && me && state.labelDecisions[me.id])

  return {
    id: state.id,
    roomCode: state.roomCode,
    gameMode: state.gameMode,
    witchSelfHeal: state.witchSelfHeal,
    speakDuration: state.speakDuration,
    bidDuration: state.bidDuration,
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
    labelCheckpoint,
    labelMeDecided,
    labelDecidedCount,
    labelDecidedTotal,
    isSandbox: state.isSandbox,
  }
}
