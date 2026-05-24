import type { Server, Socket } from 'socket.io'
import type { ServerToClientEvents, ClientToServerEvents, Role, GameState, WolfArenaState, ConversationContext, DayVoteOutcome, ChatMessage, Phase } from '@/types/game'
import { SKIP_VOTE, WOLF_VOTE_NOBODY } from '@/types/game'
import {
  getGame, saveGame, resetNightActions,
  areNightActionsDone, areDayVotesDone, areMayorVotesDone,
  buildClientState,
} from '@/server/game/state'
import {
  assignRoles, checkWinCondition,
  resolveWerewolfKill, resolveDayVote, resolveMayorElection,
  resolveDayVoteArena,
} from '@/server/game/roles'
import { prisma } from '@/lib/prisma'

type GameSocket = Socket<ClientToServerEvents, ServerToClientEvents>
type GameServer = Server<ClientToServerEvents, ServerToClientEvents>

const DAY_DISCUSSION_MS = 2 * 60 * 1000
const DAY_VOTE_MS = 60 * 1000
const MAYOR_ELECTION_MS = 60 * 1000
const DAY_RESULT_MS = 8 * 1000

// Arena pacing
const ADVOCACY_WINDOW_MS = 30 * 1000
const BID_WINDOW_MS = 60 * 1000
const SPEAK_WINDOW_MS = 30 * 1000
const MAYOR_RUNOFF_MS = 30 * 1000
const MAYOR_TIEBREAK_MS = 30 * 1000
const MAYOR_DISCUSSION_ROUNDS = 4
const DAY_DISCUSSION_ROUNDS = 8

// Anonymous labeling break: pushes the current phase's deadline back so
// players can fill in trust labels. One break per phase+round.
const LABELING_BREAK_MS = 30 * 1000
const BREAK_PHASES = new Set<Phase>([
  'day_discussion', 'day_vote', 'mayor_election', 'day_result',
])

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
  await persistSystem(io, state, `Night ${state.round} begins.`, 'NIGHT')
}

async function transitionToMayorElection(
  io: GameServer,
  roomCode: string,
  postPhase: 'day_discussion' | 'night'
) {
  clearPhaseTimer(roomCode)
  const state = await getGame(roomCode)
  if (!state) return

  state.mayorVotes = {}
  state.postElectionPhase = postPhase

  if (state.gameMode === 'arena') {
    // Arena: advocacy → conversation (4 rounds) → vote
    const aliveIds = state.players.filter(p => p.isAlive).map(p => p.id)
    const order = [...aliveIds].sort(() => Math.random() - 0.5)
    state.phase = 'mayor_advocacy'
    state.advocacy = {
      active: true,
      order,
      turn: 0,
      endTime: Date.now() + ADVOCACY_WINDOW_MS,
    }
    state.phaseEndTime = null
    await saveGame(state)
    await persistSystem(io, state, 'Mayor election begins. Each player makes one statement, in turn.', 'DAY')
    await broadcastState(io, roomCode)
    scheduleAdvocacyTimer(io, roomCode)
    return
  }

  // Classic
  state.phase = 'mayor_election'
  state.phaseEndTime = Date.now() + MAYOR_ELECTION_MS

  await saveGame(state)
  await persistSystem(io, state, 'The village must elect a Mayor.', 'DAY')
  await broadcastState(io, roomCode)

  const timer = setTimeout(() => {
    phaseTimers.delete(roomCode)
    finalizeMayorElection(io, roomCode)
  }, MAYOR_ELECTION_MS)
  phaseTimers.set(roomCode, timer)
}

// ── Arena: advocacy ──────────────────────────────────────────────────────────

function scheduleAdvocacyTimer(io: GameServer, roomCode: string) {
  const timer = setTimeout(() => {
    phaseTimers.delete(roomCode)
    advanceAdvocacy(io, roomCode, true)
  }, ADVOCACY_WINDOW_MS)
  phaseTimers.set(roomCode, timer)
}

async function advanceAdvocacy(io: GameServer, roomCode: string, fromTimer: boolean) {
  clearPhaseTimer(roomCode)
  const state = await getGame(roomCode)
  if (!state || !state.advocacy?.active || state.phase !== 'mayor_advocacy') return

  // Skip past dead or disconnected-no-message advocates by advancing until we find an alive turn
  state.advocacy.turn += 1
  while (
    state.advocacy.turn < state.advocacy.order.length &&
    !state.players.find(p => p.id === state.advocacy!.order[state.advocacy!.turn])?.isAlive
  ) {
    state.advocacy.turn += 1
  }

  if (state.advocacy.turn >= state.advocacy.order.length) {
    // Done with advocacy → start conversation
    state.advocacy = null
    state.phase = 'mayor_election'
    await saveGame(state)
    await persistSystem(io, state, 'Open discussion begins.', 'DAY')
    await startConversation(io, roomCode, 'mayor', MAYOR_DISCUSSION_ROUNDS)
    return
  }

  state.advocacy.endTime = Date.now() + ADVOCACY_WINDOW_MS
  await saveGame(state)
  await broadcastState(io, roomCode)
  scheduleAdvocacyTimer(io, roomCode)
  void fromTimer
}

// ── Arena: conversation (bid → speak cycle) ──────────────────────────────────

async function startConversation(
  io: GameServer,
  roomCode: string,
  context: ConversationContext,
  maxRounds: number,
) {
  clearPhaseTimer(roomCode)
  const state = await getGame(roomCode)
  if (!state) return

  state.conversation = {
    active: true,
    context,
    round: 1,
    maxRounds,
    sub: 'bid',
    bids: {},
    bidEndTime: Date.now() + BID_WINDOW_MS,
    speakerId: null,
    speakerName: null,
    speakerEndTime: null,
    pendingSpeakers: [],
    history: [],
  }
  state.phaseEndTime = null
  await saveGame(state)
  await broadcastState(io, roomCode)

  const timer = setTimeout(() => {
    phaseTimers.delete(roomCode)
    resolveBid(io, roomCode)
  }, BID_WINDOW_MS)
  phaseTimers.set(roomCode, timer)
}

async function resolveBid(io: GameServer, roomCode: string) {
  clearPhaseTimer(roomCode)
  const state = await getGame(roomCode)
  if (!state || !state.conversation?.active || state.conversation.sub !== 'bid') return
  const c = state.conversation

  // Default un-submitted bids to 1 (alive players only).
  const alive = state.players.filter(p => p.isAlive)
  if (alive.length === 0) {
    // No one alive: end conversation.
    await finishConversation(io, roomCode)
    return
  }
  const effective = new Map<string, number>()
  for (const p of alive) {
    effective.set(p.id, c.bids[p.id] ?? 1)
  }
  let maxBid = -Infinity
  for (const v of effective.values()) if (v > maxBid) maxBid = v
  const top: string[] = []
  for (const [id, v] of effective) if (v === maxBid) top.push(id)
  const speakerId = top[Math.floor(Math.random() * top.length)]
  const speaker = state.players.find(p => p.id === speakerId)

  c.sub = 'speak'
  c.speakerId = speakerId
  c.speakerName = speaker?.name ?? '?'
  c.speakerEndTime = Date.now() + SPEAK_WINDOW_MS
  c.bidEndTime = null
  await saveGame(state)
  await broadcastState(io, roomCode)

  const timer = setTimeout(() => {
    phaseTimers.delete(roomCode)
    endSpeak(io, roomCode)
  }, SPEAK_WINDOW_MS)
  phaseTimers.set(roomCode, timer)
}

async function endSpeak(io: GameServer, roomCode: string) {
  clearPhaseTimer(roomCode)
  const state = await getGame(roomCode)
  if (!state || !state.conversation?.active || state.conversation.sub !== 'speak') return
  const c = state.conversation

  if (c.speakerId && c.speakerName) {
    c.history.push({ round: c.round, speakerId: c.speakerId, speakerName: c.speakerName })
  }

  if (c.round >= c.maxRounds) {
    await finishConversation(io, roomCode)
    return
  }

  c.round += 1

  // Drop dead/missing players from the mention queue before deciding the next slot.
  c.pendingSpeakers = (c.pendingSpeakers ?? []).filter(id => {
    const p = state.players.find(pp => pp.id === id)
    return !!p && p.isAlive
  })

  if (c.pendingSpeakers.length > 0) {
    // Mentioned player goes next — skip the bid window.
    const nextId = c.pendingSpeakers.shift()!
    const next = state.players.find(p => p.id === nextId)
    c.sub = 'speak'
    c.bids = {}
    c.bidEndTime = null
    c.speakerId = nextId
    c.speakerName = next?.name ?? '?'
    c.speakerEndTime = Date.now() + SPEAK_WINDOW_MS
    await saveGame(state)
    await broadcastState(io, roomCode)

    const timer = setTimeout(() => {
      phaseTimers.delete(roomCode)
      endSpeak(io, roomCode)
    }, SPEAK_WINDOW_MS)
    phaseTimers.set(roomCode, timer)
    return
  }

  c.sub = 'bid'
  c.bids = {}
  c.bidEndTime = Date.now() + BID_WINDOW_MS
  c.speakerId = null
  c.speakerName = null
  c.speakerEndTime = null
  await saveGame(state)
  await broadcastState(io, roomCode)

  const timer = setTimeout(() => {
    phaseTimers.delete(roomCode)
    resolveBid(io, roomCode)
  }, BID_WINDOW_MS)
  phaseTimers.set(roomCode, timer)
}

async function finishConversation(io: GameServer, roomCode: string) {
  clearPhaseTimer(roomCode)
  const state = await getGame(roomCode)
  if (!state || !state.conversation) return
  const context = state.conversation.context
  state.conversation = null

  if (context === 'mayor') {
    // Open the vote portion of the mayor election.
    state.mayorVotes = {}
    state.phaseEndTime = Date.now() + MAYOR_ELECTION_MS
    await saveGame(state)
    await persistSystem(io, state, 'Mayor vote begins.', 'DAY')
    await broadcastState(io, roomCode)
    const timer = setTimeout(() => {
      phaseTimers.delete(roomCode)
      finalizeMayorElection(io, roomCode)
    }, MAYOR_ELECTION_MS)
    phaseTimers.set(roomCode, timer)
  } else {
    // 'day' → day vote
    await saveGame(state)
    await transitionToDayVote(io, roomCode)
  }
}

// Called by chat handler when speaker sends their message (or advocate sends theirs).
export async function onSpeakerMessage(
  io: GameServer,
  roomCode: string,
  senderId: string,
  content: string,
): Promise<void> {
  const state = await getGame(roomCode)
  if (!state) return

  if (state.phase === 'mayor_advocacy' && state.advocacy?.active) {
    const currentId = state.advocacy.order[state.advocacy.turn]
    if (currentId !== senderId) return
    await advanceAdvocacy(io, roomCode, false)
    return
  }

  if (state.conversation?.active && state.conversation.sub === 'speak') {
    if (state.conversation.speakerId !== senderId) return

    // Enqueue any newly mentioned alive players (skip the speaker themselves and
    // anyone already queued). Persist before endSpeak reads state.
    const mentioned = findMentions(content, state.players, senderId)
    if (mentioned.length > 0) {
      const c = state.conversation
      const queue = c.pendingSpeakers ?? []
      const seen = new Set(queue)
      for (const id of mentioned) {
        if (!seen.has(id)) {
          queue.push(id)
          seen.add(id)
        }
      }
      c.pendingSpeakers = queue
      await saveGame(state)
    }

    await endSpeak(io, roomCode)
    return
  }
}

// Match alive player names as whole tokens in `content`, case-insensitive.
// Excludes the speaker. Returns IDs in the order they first appear in the message.
function findMentions(content: string, players: GameState['players'], speakerId: string): string[] {
  const lower = content.toLowerCase()
  type Hit = { id: string; at: number }
  const hits: Hit[] = []
  for (const p of players) {
    if (!p.isAlive) continue
    if (p.id === speakerId) continue
    const name = p.name.trim().toLowerCase()
    if (!name) continue
    let from = 0
    let at = -1
    while (from <= lower.length) {
      const idx = lower.indexOf(name, from)
      if (idx === -1) break
      const before = idx === 0 ? '' : lower[idx - 1]
      const after = idx + name.length >= lower.length ? '' : lower[idx + name.length]
      const beforeOk = !before || !/[a-z0-9_]/.test(before)
      const afterOk = !after || !/[a-z0-9_]/.test(after)
      if (beforeOk && afterOk) { at = idx; break }
      from = idx + 1
    }
    if (at !== -1) hits.push({ id: p.id, at })
  }
  hits.sort((a, b) => a.at - b.at)
  return hits.map(h => h.id)
}

async function finalizeMayorElection(io: GameServer, roomCode: string) {
  clearPhaseTimer(roomCode)
  const state = await getGame(roomCode)
  if (!state || state.phase !== 'mayor_election') return

  // Arena: published individual votes + runoff on tie.
  if (state.gameMode === 'arena') {
    const counts: Record<string, number> = {}
    for (const target of Object.values(state.mayorVotes)) {
      counts[target] = (counts[target] || 0) + 1
    }
    const sorted = Object.entries(counts).sort((a, b) => b[1] - a[1])

    if (sorted.length === 0) {
      // No one voted: skip and proceed without electing a mayor.
      await persistSystem(io, state, 'No one voted. No Mayor elected.', 'DAY')
      await proceedAfterMayorElection(io, state)
      return
    }

    const topScore = sorted[0][1]
    const tied = sorted.filter(([, v]) => v === topScore).map(([k]) => k)

    // Persist individual votes message.
    if (state.dbGameId) {
      const lines = Object.entries(state.mayorVotes).map(([voter, target]) => {
        const v = state.players.find(p => p.id === voter)?.name ?? '?'
        const t = state.players.find(p => p.id === target)?.name ?? '?'
        return `${v} → ${t}`
      })
      const summary = `Mayor vote results: ${lines.join(', ')}`
      await persistSystem(io, state, summary, 'DAY')
    }

    if (tied.length === 1) {
      state.mayorId = tied[0]
      const name = state.players.find(p => p.id === state.mayorId)?.name ?? 'Someone'
      state.mayorElected = true
      await persistSystem(io, state, `${name} has been elected Mayor. The Mayor breaks ties in day votes.`, 'DAY')
      await proceedAfterMayorElection(io, state)
      return
    }

    // Tied → runoff
    state.mayorRunoff = {
      active: true,
      candidates: tied,
      votes: {},
      endTime: Date.now() + MAYOR_RUNOFF_MS,
    }
    state.phaseEndTime = Date.now() + MAYOR_RUNOFF_MS
    await saveGame(state)
    const names = tied.map(id => state.players.find(p => p.id === id)?.name ?? '?').join(', ')
    await persistSystem(io, state, `Mayor vote tied between ${names}. Runoff begins.`, 'DAY')
    await broadcastState(io, roomCode)
    const timer = setTimeout(() => {
      phaseTimers.delete(roomCode)
      resolveMayorRunoff(io, roomCode)
    }, MAYOR_RUNOFF_MS)
    phaseTimers.set(roomCode, timer)
    return
  }

  // Classic
  const winnerId = resolveMayorElection(state.mayorVotes)

  if (winnerId) {
    state.mayorId = winnerId
    const name = state.players.find(p => p.id === winnerId)?.name ?? 'Someone'
    state.mayorElected = true
    await persistSystem(io, state, `${name} has been elected Mayor. Their vote counts double.`, 'DAY')
  }

  await proceedAfterMayorElection(io, state)
}

async function proceedAfterMayorElection(io: GameServer, state: GameState) {
  const next = state.postElectionPhase ?? 'day_discussion'
  state.postElectionPhase = null

  if (next === 'day_discussion') {
    await startDayDiscussion(io, state)
  } else {
    await saveGame(state)
    await transitionToNight(io, state.roomCode)
  }
}

async function resolveMayorRunoff(io: GameServer, roomCode: string) {
  clearPhaseTimer(roomCode)
  const state = await getGame(roomCode)
  if (!state || !state.mayorRunoff?.active) return

  const counts: Record<string, number> = {}
  for (const target of Object.values(state.mayorRunoff.votes)) {
    counts[target] = (counts[target] || 0) + 1
  }
  const sorted = Object.entries(counts).sort((a, b) => b[1] - a[1])

  let winnerId: string | null = null
  if (sorted.length === 0) {
    // No votes: random among candidates.
    const cands = state.mayorRunoff.candidates
    winnerId = cands[Math.floor(Math.random() * cands.length)]
  } else {
    const topScore = sorted[0][1]
    const tied = sorted.filter(([, v]) => v === topScore).map(([k]) => k)
    winnerId = tied[Math.floor(Math.random() * tied.length)]
  }

  state.mayorRunoff = null
  state.mayorId = winnerId
  state.mayorElected = true
  state.phaseEndTime = null

  const name = state.players.find(p => p.id === winnerId)?.name ?? 'Someone'
  await persistSystem(io, state, `Runoff result: ${name} elected Mayor.`, 'DAY')

  await proceedAfterMayorElection(io, state)
}

async function startDayDiscussion(io: GameServer, state: GameState) {
  state.phase = 'day_discussion'
  state.dayVotes = { votes: {} }

  if (state.gameMode === 'arena') {
    state.phaseEndTime = null
    await saveGame(state)
    await broadcastState(io, state.roomCode)
    await persistSystem(io, state, `Day ${state.round} discussion begins. ${DAY_DISCUSSION_ROUNDS} bid-to-speak rounds.`, 'DAY')
    await startConversation(io, state.roomCode, 'day', DAY_DISCUSSION_ROUNDS)
    return
  }

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

  // killTarget was set when the wolves' vote resolved (classic: when all voted;
  // arena: after round 3). Trust it instead of re-deriving.
  const killTargetId = state.nightActions.killTarget
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
    await persistSystem(io, state, systemMsg, 'DAY')
    await broadcastState(io, state.roomCode)
    return
  }

  await persistSystem(io, state, systemMsg, 'DAY')

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
  await persistSystem(io, state, 'Voting begins.', 'DAY')
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

  if (state.gameMode === 'arena') {
    const { outcome, eliminatedId, tieCandidates } = resolveDayVoteArena(state.dayVotes.votes)
    if (outcome === 'tie' && tieCandidates && tieCandidates.length > 1) {
      const mayor = state.mayorId ? state.players.find(p => p.id === state.mayorId) : null
      if (mayor && mayor.isAlive) {
        // Mayor decides: hand off to tiebreak phase (still day_vote phase).
        state.pendingMayorTiebreak = tieCandidates
        state.phaseEndTime = Date.now() + MAYOR_TIEBREAK_MS
        await saveGame(state)
        const names = tieCandidates.map(id => state.players.find(p => p.id === id)?.name ?? '?').join(', ')
        await persistSystem(io, state, `The vote tied between ${names}. ${mayor.name} (Mayor) will break the tie.`, 'DAY')
        await broadcastState(io, roomCode)
        const timer = setTimeout(() => {
          phaseTimers.delete(roomCode)
          applyMayorTiebreak(io, roomCode, null)
        }, MAYOR_TIEBREAK_MS)
        phaseTimers.set(roomCode, timer)
        return
      }
      // No mayor → tie stands, no one eliminated.
      await applyDayElimination(io, roomCode, null, 'tie')
      return
    }
    await applyDayElimination(io, roomCode, eliminatedId, outcome)
    return
  }

  // Classic
  const { outcome, eliminatedId } = resolveDayVote(state.dayVotes.votes, state.mayorId)
  await applyDayElimination(io, roomCode, eliminatedId, outcome)
}

async function applyMayorTiebreak(
  io: GameServer,
  roomCode: string,
  decision: string | null,
) {
  clearPhaseTimer(roomCode)
  const state = await getGame(roomCode)
  if (!state || !state.pendingMayorTiebreak) return

  const candidates = state.pendingMayorTiebreak
  state.pendingMayorTiebreak = null

  const eliminatedId = decision && candidates.includes(decision) ? decision : null
  const outcome: DayVoteOutcome = eliminatedId ? 'eliminated' : 'tie'

  if (state.dbGameId) {
    const mayorName = state.mayorId ? (state.players.find(p => p.id === state.mayorId)?.name ?? 'Mayor') : 'Mayor'
    if (eliminatedId) {
      const tname = state.players.find(p => p.id === eliminatedId)?.name ?? '?'
      await persistSystem(io, state, `${mayorName} (Mayor) broke the tie: ${tname} is exiled.`, 'DAY')
    } else {
      await persistSystem(io, state, `${mayorName} (Mayor) declined to break the tie. No one is exiled.`, 'DAY')
    }
  }

  await applyDayElimination(io, roomCode, eliminatedId, outcome)
}

async function applyDayElimination(
  io: GameServer,
  roomCode: string,
  eliminatedId: string | null,
  outcome: DayVoteOutcome,
) {
  const state = await getGame(roomCode)
  if (!state) return

  let systemMsg = ''
  state.lastEliminated = null
  state.dayVoteOutcome = outcome

  if (eliminatedId && outcome === 'eliminated') {
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
    await persistSystem(io, state, systemMsg, 'DAY')
    await broadcastState(io, roomCode)
    return
  }

  await persistSystem(io, state, systemMsg, 'DAY')

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

const DAY_LIKE_PHASES = new Set<Phase>([
  'mayor_advocacy', 'mayor_election', 'day_discussion', 'day_vote', 'day_result',
])

// Persist a system message to the DB *and* broadcast it to all players in the
// room so the chronological event log is visible client-side (used by the
// trust-labeling survey to pick the event being labeled).
async function persistSystem(
  io: GameServer,
  state: GameState,
  content: string,
  dbPhase: 'DAY' | 'NIGHT',
) {
  if (!state.dbGameId) return
  try {
    const created = await prisma.message.create({
      data: {
        gameId: state.dbGameId,
        playerName: 'System',
        content,
        phase: dbPhase,
        round: state.round,
        isSystem: true,
      },
    })
    // Pick a granular broadcast phase: night messages tag as 'night'; day
    // messages prefer the current state phase, falling back to a generic
    // daytime tag when state has already moved on (dawn announcements, etc.).
    const broadcastPhase: Phase =
      dbPhase === 'NIGHT'
        ? 'night'
        : DAY_LIKE_PHASES.has(state.phase) ? state.phase : 'day_discussion'
    const msg: ChatMessage = {
      id: created.id,
      playerId: null,
      playerName: 'System',
      role: null,
      content,
      phase: broadcastPhase,
      round: state.round,
      isSystem: true,
      timestamp: created.createdAt.getTime(),
    }
    io.to(`room:${state.roomCode}`).emit('chat:message', msg)
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

// Maps the current phase to the function that should fire when its timer
// expires. Used to (re)schedule the phase deadline after a labeling break.
function schedulePhaseTimer(io: GameServer, roomCode: string, state: GameState) {
  if (!state.phaseEndTime) return
  const delay = Math.max(0, state.phaseEndTime - Date.now())
  let fn: (() => void) | null = null
  switch (state.phase) {
    case 'day_discussion':
      fn = () => { transitionToDayVote(io, roomCode) }
      break
    case 'day_vote':
      fn = () => { resolveVoteAndAdvance(io, roomCode) }
      break
    case 'mayor_election':
      // Only classic mayor election uses phaseEndTime in this way. In Arena,
      // when the conversation is active, phaseEndTime is null; once it ends
      // and the vote opens, phaseEndTime is set and this branch handles it.
      fn = () => { finalizeMayorElection(io, roomCode) }
      break
    case 'day_result':
      fn = () => { transitionAfterDayResult(io, roomCode) }
      break
  }
  if (!fn) return
  const timer = setTimeout(() => {
    phaseTimers.delete(roomCode)
    fn!()
  }, delay)
  phaseTimers.set(roomCode, timer)
}

async function startLabelingBreak(io: GameServer, roomCode: string): Promise<{ ok: boolean; error?: string }> {
  const state = await getGame(roomCode)
  if (!state) return { ok: false, error: 'Game not found' }
  if (!BREAK_PHASES.has(state.phase)) return { ok: false, error: 'Breaks are not allowed in this phase' }
  if (state.labelingBreak?.active) return { ok: false, error: 'A labeling break is already in progress' }
  if (state.conversation?.active || state.advocacy?.active || state.mayorRunoff?.active || state.pendingMayorTiebreak) {
    return { ok: false, error: 'Cannot pause during the current sub-phase' }
  }
  const key = `${state.phase}:${state.round}`
  const used = state.labelingBreakUsed ?? []
  if (used.includes(key)) return { ok: false, error: 'A break has already been used this phase' }

  clearPhaseTimer(roomCode)

  const now = Date.now()
  const breakEnd = now + LABELING_BREAK_MS
  state.phaseEndTime = (state.phaseEndTime ?? now) + LABELING_BREAK_MS
  state.labelingBreak = { active: true, endTime: breakEnd }
  state.labelingBreakUsed = [...used, key]

  await saveGame(state)
  await broadcastState(io, roomCode)
  await persistSystem(io, state, 'A labeling break has been called. The phase deadline is pushed back 30 seconds.', 'DAY')

  // After the break ends, clear the flag, then reschedule the phase timer for
  // the remaining (now extended) time.
  const breakTimer = setTimeout(async () => {
    phaseTimers.delete(roomCode)
    const s = await getGame(roomCode)
    if (!s) return
    s.labelingBreak = null
    await saveGame(s)
    await broadcastState(io, roomCode)
    schedulePhaseTimer(io, roomCode, s)
  }, LABELING_BREAK_MS)
  phaseTimers.set(roomCode, breakTimer)

  return { ok: true }
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
      gameMode: state.gameMode === 'arena' ? 'ARENA' : 'CLASSIC',
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

      const aliveWolves = state.players.filter(p => p.role === 'werewolf' && p.isAlive)
      const isArena = state.gameMode === 'arena'
      const nobody = targetId === WOLF_VOTE_NOBODY

      // Validate target: 'nobody' is only allowed in arena mode; otherwise must be a non-wolf alive player.
      if (nobody) {
        if (!isArena) return
      } else {
        const target = state.players.find(p => p.id === targetId && p.isAlive && p.role !== 'werewolf')
        if (!target) return
      }

      const targetName = nobody
        ? null
        : state.players.find(p => p.id === targetId)?.name ?? null

      let arenaJustResolved: WolfArenaState | null = null

      if (isArena && aliveWolves.length > 1 && state.nightActions.wolfArena) {
        // ── Arena sequential vote ────────────────────────────────────────────
        const arena = state.nightActions.wolfArena
        if (arena.resolved) return
        if (arena.order[arena.turn] !== voter.id) return
        if (arena.currentVotes[voter.id]) return  // double-submit guard

        arena.currentVotes[voter.id] = targetId
        arena.turn += 1

        if (arena.turn >= arena.order.length) {
          // Round complete: archive and decide whether to continue.
          arena.history.push({ round: arena.round, votes: { ...arena.currentVotes } })

          if (arena.round >= 3) {
            const finalVotes = arena.currentVotes
            const distinct = new Set(Object.values(finalVotes))
            const unanimous = distinct.size === 1 ? [...distinct][0] : null
            const kill = unanimous && unanimous !== WOLF_VOTE_NOBODY ? unanimous : null

            state.nightActions.killTarget = kill
            state.nightActions.werewolfVotes = { ...finalVotes }
            state.nightActions.completed.werewolves = true
            arena.resolved = true
            arenaJustResolved = arena
          } else {
            arena.round += 1
            arena.turn = 0
            arena.currentVotes = {}
          }
        }
      } else {
        // ── Classic or arena solo-wolf ───────────────────────────────────────
        if (nobody && aliveWolves.length === 1) {
          state.nightActions.werewolfVotes[playerId] = WOLF_VOTE_NOBODY
          state.nightActions.killTarget = null
          state.nightActions.completed.werewolves = true
        } else {
          state.nightActions.werewolfVotes[playerId] = targetId
          if (aliveWolves.every(w => !!state.nightActions.werewolfVotes[w.id])) {
            state.nightActions.completed.werewolves = true
            state.nightActions.killTarget = resolveWerewolfKill(state.nightActions.werewolfVotes)
          }
        }
      }

      // Persistence
      if (state.dbGameId) {
        if (arenaJustResolved) {
          // Write one row per wolf's final-round vote. Skip 'nobody'.
          for (const [wolfId, target] of Object.entries(arenaJustResolved.currentVotes)) {
            if (target === WOLF_VOTE_NOBODY) continue
            const wolfName = state.players.find(p => p.id === wolfId)?.name
            const tName = state.players.find(p => p.id === target)?.name
            if (!wolfName || !tName) continue
            await prisma.nightAction.create({
              data: {
                gameId: state.dbGameId,
                playerId: await getDbPlayerId(state.dbGameId, wolfName),
                actionType: 'KILL',
                targetPlayerId: await getDbPlayerId(state.dbGameId, tName),
                round: state.round,
              },
            }).catch(() => {})
          }
        } else if (!(isArena && aliveWolves.length > 1) && targetName) {
          // Classic or arena-solo: original upsert behavior (allows changing vote).
          await prisma.nightAction.upsert({
            where: { id: `${state.dbGameId}-${playerId}-${state.round}-kill` },
            create: { id: `${state.dbGameId}-${playerId}-${state.round}-kill`, gameId: state.dbGameId, playerId: await getDbPlayerId(state.dbGameId, voter.name), actionType: 'KILL', targetPlayerId: await getDbPlayerId(state.dbGameId, targetName), round: state.round },
            update: { targetPlayerId: await getDbPlayerId(state.dbGameId, targetName) },
          }).catch(() => {})
        }
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
      // Arena: vote is only open once discussion ends and before runoff begins.
      if (state.gameMode === 'arena' && (state.conversation?.active || state.mayorRunoff?.active)) return

      const voter = state.players.find(p => p.id === playerId)
      if (!voter || !voter.isAlive) return

      // Arena allows self-vote (players advocate for themselves); classic does not.
      const allowSelf = state.gameMode === 'arena'
      const target = state.players.find(p => p.id === targetId && p.isAlive && (allowSelf || p.id !== playerId))
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
      else if (state.phase === 'mayor_advocacy') await advanceAdvocacy(io, roomCode, false)
      else if (state.phase === 'mayor_election') {
        if (state.mayorRunoff?.active) await resolveMayorRunoff(io, roomCode)
        else if (state.conversation?.active && state.conversation.sub === 'bid') await resolveBid(io, roomCode)
        else if (state.conversation?.active && state.conversation.sub === 'speak') await endSpeak(io, roomCode)
        else await finalizeMayorElection(io, roomCode)
      }
      else if (state.phase === 'day_discussion') {
        if (state.conversation?.active && state.conversation.sub === 'bid') await resolveBid(io, roomCode)
        else if (state.conversation?.active && state.conversation.sub === 'speak') await endSpeak(io, roomCode)
        else await transitionToDayVote(io, roomCode)
      }
      else if (state.phase === 'day_vote') {
        if (state.pendingMayorTiebreak) await applyMayorTiebreak(io, roomCode, null)
        else await resolveVoteAndAdvance(io, roomCode)
      }
      else if (state.phase === 'day_result') await transitionAfterDayResult(io, roomCode)
    } catch (err) { console.error('[phase:advance]', err) }
  })

  socket.on('conversation:bid', async (bid) => {
    try {
      const { playerId, roomCode } = socket.data
      const state = await getGame(roomCode)
      if (!state || !state.conversation?.active || state.conversation.sub !== 'bid') return
      const player = state.players.find(p => p.id === playerId)
      if (!player?.isAlive) return
      if (!Number.isFinite(bid) || bid < 1 || bid > 5) return
      state.conversation.bids[playerId] = Math.floor(bid)

      // Early-resolve when every alive player has bid.
      const aliveIds = state.players.filter(p => p.isAlive).map(p => p.id)
      const allBid = aliveIds.every(id => state.conversation!.bids[id] !== undefined)

      await saveGame(state)
      if (allBid) await resolveBid(io, roomCode)
      else await broadcastState(io, roomCode)
    } catch (err) { console.error('[conversation:bid]', err) }
  })

  socket.on('mayor:runoff_vote', async (candidateId) => {
    try {
      const { playerId, roomCode } = socket.data
      const state = await getGame(roomCode)
      if (!state || !state.mayorRunoff?.active) return
      const voter = state.players.find(p => p.id === playerId)
      if (!voter?.isAlive) return
      if (!state.mayorRunoff.candidates.includes(candidateId)) return

      state.mayorRunoff.votes[playerId] = candidateId
      await saveGame(state)

      const alive = state.players.filter(p => p.isAlive)
      if (alive.every(p => state.mayorRunoff!.votes[p.id] !== undefined)) {
        await resolveMayorRunoff(io, roomCode)
      } else {
        await broadcastState(io, roomCode)
      }
    } catch (err) { console.error('[mayor:runoff_vote]', err) }
  })

  socket.on('mayor:tiebreak_decision', async (targetId) => {
    try {
      const { playerId, roomCode } = socket.data
      const state = await getGame(roomCode)
      if (!state || !state.pendingMayorTiebreak) return
      const mayor = state.players.find(p => p.id === playerId)
      if (!mayor || mayor.id !== state.mayorId || !mayor.isAlive) return
      if (targetId !== null && !state.pendingMayorTiebreak.includes(targetId)) return
      await applyMayorTiebreak(io, roomCode, targetId)
    } catch (err) { console.error('[mayor:tiebreak_decision]', err) }
  })

  socket.on('label:request_break', async (cb) => {
    const ack = typeof cb === 'function' ? cb : () => {}
    try {
      const { playerId, roomCode } = socket.data
      if (!playerId || !roomCode) return ack({ success: false, error: 'Not in a room' })
      const state = await getGame(roomCode)
      if (!state) return ack({ success: false, error: 'No game' })
      const player = state.players.find(p => p.id === playerId)
      if (!player?.isAlive) return ack({ success: false, error: 'Only alive players can request a break' })
      const r = await startLabelingBreak(io, roomCode)
      if (!r.ok) return ack({ success: false, error: r.error })
      ack({ success: true })
    } catch (err) {
      console.error('[label:request_break]', err)
      ack({ success: false, error: 'Failed to start break' })
    }
  })
}
