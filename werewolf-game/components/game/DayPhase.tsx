'use client'

import { useState, useEffect } from 'react'
import type { ClientGameState, ChatMessage } from '@/types/game'
import { SKIP_VOTE } from '@/types/game'
import type { GameSocket } from '@/app/room/[code]/page'
import Button from '@/components/ui/Button'
import Chat from './Chat'
import PlayerName from './PlayerName'
import ConversationPanel from './ConversationPanel'
import { safeDateNow } from '@/lib/clock'

interface Props {
  state: ClientGameState
  socket: GameSocket
  messages: ChatMessage[]
}

function useCountdown(endTime: number | null) {
  const [remaining, setRemaining] = useState<number>(0)

  useEffect(() => {
    if (!endTime) return
    const tick = () => setRemaining(Math.max(0, endTime - safeDateNow()))
    tick()
    const id = setInterval(tick, 500)
    return () => clearInterval(id)
  }, [endTime])

  const minutes = Math.floor(remaining / 60000)
  const seconds = Math.floor((remaining % 60000) / 1000)
  return { remaining, label: `${minutes}:${String(seconds).padStart(2, '0')}` }
}

export default function DayPhase({ state, socket, messages }: Props) {
  const [selected, setSelected] = useState<string | null>(null)
  const me = state.players.find(p => p.id === state.myId)
  const isAlive = me?.isAlive ?? false
  const isVoting = state.phase === 'day_vote'
  const isHost = me?.isHost
  // System messages (e.g. "Night 2 begins.") are public and tagged with the
  // phase they were emitted in — keep them so the day-chat log shows the full
  // arc, including night transitions. Private wolf-pack chat is non-system.
  const dayMessages = messages.filter(m => m.phase !== 'night' || m.isSystem)
  const countdown = useCountdown(state.phaseEndTime)
  const isArena = state.gameMode === 'arena'
  const inConversation = !!state.conversation?.active
  const isSpeaker = state.conversation?.sub === 'speak' && state.conversation.speakerId === state.myId
  const tiebreakPending = !!state.mayorTiebreakPending
  const isMayor = state.mayorId === state.myId

  const myVoteTargetId = state.dayVotes[state.myId]
  const myVoteTarget = state.players.find(p => p.id === myVoteTargetId)

  // Vote tally: arena uses 1x for mayor; classic uses 2x.
  const tally: Record<string, number> = {}
  for (const [voterId, targetId] of Object.entries(state.dayVotes)) {
    const weight = isArena ? 1 : (voterId === state.mayorId ? 2 : 1)
    tally[targetId] = (tally[targetId] || 0) + weight
  }

  // Map: targetId → list of voter names
  const voterNames: Record<string, string[]> = {}
  for (const [voterId, targetId] of Object.entries(state.dayVotes)) {
    const voterName = state.players.find(p => p.id === voterId)?.name ?? '?'
    if (!voterNames[targetId]) voterNames[targetId] = []
    voterNames[targetId].push(voterName + (!isArena && voterId === state.mayorId ? ' ×2' : ''))
  }

  const skipVotes = tally[SKIP_VOTE] || 0
  const skipVoters = voterNames[SKIP_VOTE] || []

  function handleVote(targetId: string) {
    setSelected(targetId)
    socket.emit('day:vote', targetId)
  }

  // Day Result outcomes
  const outcome = state.dayVoteOutcome
  const victim = state.lastEliminated

  let resultIcon = '🌑'
  let resultHeadline = ''
  let resultBody: React.ReactNode = null
  let resultTone = 'border-slate-700 bg-slate-900'

  if (outcome === 'eliminated' && victim) {
    resultIcon = '⚖️'
    resultHeadline = `${victim.playerName} has been eliminated`
    resultBody = (
      <p className="text-slate-300 mt-1 text-xs">
        They were a <span className="font-semibold capitalize text-slate-100">{victim.role}</span>.
      </p>
    )
    resultTone = 'border-red-800 bg-red-950/40'
  } else if (outcome === 'skipped') {
    resultIcon = '⏭'
    resultHeadline = 'The village chose to skip'
    resultBody = <p className="text-slate-300 mt-1 text-xs">No one was eliminated today.</p>
    resultTone = 'border-amber-800 bg-amber-950/40'
  } else if (outcome === 'tie') {
    resultIcon = '⚖️'
    resultHeadline = 'The vote was tied'
    resultBody = <p className="text-slate-300 mt-1 text-xs">No one was eliminated today.</p>
    resultTone = 'border-slate-700 bg-slate-800/60'
  }

  return (
    <div className="flex flex-col lg:flex-row gap-4 h-full p-4 max-w-5xl mx-auto w-full">
      <div className="flex-1 flex flex-col gap-4 min-w-0">

        <div className="bg-slate-900 border border-slate-700 rounded-xl p-4">
          <div className="flex items-center justify-between flex-wrap gap-2">
            <div className="flex items-center gap-2">
              <span className="text-lg">☀️</span>
              <h2 className="font-bold text-slate-100">
                Day {state.round} — {state.phase === 'day_result' ? 'Result' : isVoting ? 'Voting' : 'Discussion'}
              </h2>
              {state.phaseEndTime && countdown.remaining > 0 && (
                <span className={`text-sm font-mono px-2 py-0.5 rounded ${countdown.remaining < 15000 ? 'text-red-400 bg-red-950/40' : (isVoting || state.phase === 'day_result') ? 'text-red-300 bg-red-950/30' : 'text-amber-400 bg-amber-950/40'}`}>
                  {countdown.label}
                </span>
              )}
            </div>
            <div className="flex gap-2">
              {isHost && state.phase === 'day_result' && (
                <Button size="sm" variant="ghost" onClick={() => socket.emit('phase:advance')}>
                  Continue now
                </Button>
              )}
              {isHost && !isVoting && state.phase !== 'day_result' && (
                <Button size="sm" variant="warning" onClick={() => socket.emit('phase:advance')}>
                  {isArena && inConversation ? 'Skip current step' : 'Start vote now'}
                </Button>
              )}
              {isHost && isVoting && !tiebreakPending && (
                <Button size="sm" variant="ghost" onClick={() => socket.emit('phase:advance')}>
                  Force resolve
                </Button>
              )}
            </div>
          </div>

          {state.lastEliminated && state.phase !== 'day_result' && (
            <div className="mt-3 p-3 bg-slate-800 rounded-lg border border-slate-700">
              <p className="text-sm text-slate-300">
                <span className="text-red-400 font-semibold">{state.lastEliminated.playerName}</span>
                {' '}was eliminated last night. They were a{' '}
                <span className="font-semibold">{state.lastEliminated.role}</span>.
              </p>
            </div>
          )}
        </div>

        {state.phase === 'day_result' && (
          <div className={`p-5 border rounded-xl text-center ${resultTone} flex flex-col items-center gap-1.5`}>
            <div className="text-5xl">{resultIcon}</div>
            <h3 className="text-lg font-bold text-slate-100 leading-snug">{resultHeadline}</h3>
            {resultBody}
            <div className="mt-2 text-[10px] uppercase tracking-wider text-amber-500 font-bold border-t border-slate-800/40 w-full pt-2">
              🏷️ Next: Trust Labeling
            </div>
          </div>
        )}

        {isArena && inConversation && (
          <ConversationPanel state={state} socket={socket} />
        )}

        {isArena && tiebreakPending && (
          <div className="bg-slate-900 border border-amber-700 rounded-xl p-4 flex flex-col gap-3">
            <p className="text-sm font-semibold text-amber-200">Vote tied — Mayor decides</p>
            {isMayor && state.mayorTiebreakCandidates && state.mayorTiebreakCandidates.length > 0 ? (
              <>
                <p className="text-xs text-slate-300">Pick which tied candidate to exile, or decline to break the tie.</p>
                <div className="grid grid-cols-1 gap-2">
                  {state.mayorTiebreakCandidates.map(id => {
                    const p = state.players.find(x => x.id === id)
                    if (!p) return null
                    return (
                      <button
                        key={id}
                        onClick={() => socket.emit('mayor:tiebreak_decision', id)}
                        className="text-left px-3 py-2 rounded-lg border border-slate-700 bg-slate-800/60 text-slate-200 hover:border-red-600 hover:bg-red-950/30 cursor-pointer"
                      >
                        Exile <span className="font-semibold text-red-300">{p.name}</span>
                      </button>
                    )
                  })}
                </div>
                <button
                  onClick={() => socket.emit('mayor:tiebreak_decision', null)}
                  className="text-xs px-3 py-2 bg-slate-800 hover:bg-slate-700 border border-slate-600 rounded transition-colors cursor-pointer text-slate-300"
                >
                  Decline — no one is exiled
                </button>
              </>
            ) : (
              <p className="text-xs text-slate-400">
                The Mayor is choosing the tied candidate to exile.
              </p>
            )}
          </div>
        )}

        <div className="bg-slate-900 border border-slate-700 rounded-xl p-4">
          <h3 className="text-sm font-semibold text-slate-400 uppercase tracking-wide mb-3">
            {state.phase === 'day_result' ? 'Final Votes' : isVoting ? 'Vote to eliminate' : 'Players'}
          </h3>

          <ul className="space-y-2">
            {state.players.map(p => {
              const votes = tally[p.id] || 0
              const voters = voterNames[p.id] || []
              const isSelected = (selected ?? myVoteTargetId) === p.id
              const canVote = isVoting && isAlive && p.isAlive && p.id !== state.myId && !state.labelCheckpoint

              return (
                <li
                  key={p.id}
                  onClick={() => canVote && handleVote(p.id)}
                  className={`
                    flex items-center justify-between px-3 py-2 rounded-lg border transition-colors
                    ${!p.isAlive ? 'opacity-40 border-slate-800 bg-slate-900/30' : 'border-slate-700 bg-slate-800/60'}
                    ${isSelected && isVoting ? 'border-red-500 bg-red-950/30' : ''}
                    ${canVote ? 'cursor-pointer hover:border-red-400' : ''}
                  `}
                >
                  <div className="flex items-center gap-2 min-w-0">
                    <span className="text-sm truncate">
                      <PlayerName
                        name={p.name}
                        role={p.role}
                        isMe={p.id === state.myId}
                        isHost={p.isHost}
                        isMayor={p.isMayor}
                      />
                    </span>
                  </div>
                  <div className="flex items-center gap-3 shrink-0">
                    {(isVoting || state.phase === 'day_result') && voters.length > 0 && (
                      <span className="text-xs text-slate-400 italic hidden sm:block">
                        ← {voters.join(', ')}
                      </span>
                    )}
                    {(isVoting || state.phase === 'day_result') && votes > 0 && (
                      <span className={`text-sm font-bold px-2 py-0.5 rounded ${votes >= 2 ? 'text-red-300 bg-red-950/60' : 'text-slate-300 bg-slate-700'}`}>
                        {votes}
                      </span>
                    )}
                    {p.role && (
                      <span className="text-xs text-slate-400 capitalize">{p.role}</span>
                    )}
                    {!p.isAlive && <span className="text-xs text-slate-500">☠</span>}
                  </div>
                </li>
              )
            })}
          </ul>

          {isVoting && (
            <button
              onClick={() => isAlive && !state.labelCheckpoint && handleVote(SKIP_VOTE)}
              disabled={!isAlive || !!state.labelCheckpoint}
              className={`
                mt-2 w-full flex items-center justify-between px-3 py-2 rounded-lg border transition-colors text-left
                ${myVoteTargetId === SKIP_VOTE || selected === SKIP_VOTE
                  ? 'border-amber-500 bg-amber-950/30'
                  : 'border-slate-700 bg-slate-800/60'}
                ${isAlive ? 'cursor-pointer hover:border-amber-400' : 'opacity-50 cursor-not-allowed'}
              `}
            >
              <span className="text-sm font-medium text-slate-200">
                ⏭ Skip vote
                <span className="text-xs text-slate-400 ml-2">(don't eliminate anyone)</span>
              </span>
              <div className="flex items-center gap-3 shrink-0">
                {skipVoters.length > 0 && (
                  <span className="text-xs text-slate-400 italic hidden sm:block">
                    ← {skipVoters.join(', ')}
                  </span>
                )}
                {skipVotes > 0 && (
                  <span className={`text-sm font-bold px-2 py-0.5 rounded ${skipVotes >= 2 ? 'text-amber-300 bg-amber-950/60' : 'text-slate-300 bg-slate-700'}`}>
                    {skipVotes}
                  </span>
                )}
              </div>
            </button>
          )}

          {!isVoting && state.phase === 'day_result' && (
            <div
              className={`
                mt-2 w-full flex items-center justify-between px-3 py-2 rounded-lg border text-left
                ${myVoteTargetId === SKIP_VOTE
                  ? 'border-amber-500 bg-amber-950/30'
                  : 'border-slate-700 bg-slate-800/60'}
              `}
            >
              <span className="text-sm font-medium text-slate-200">
                ⏭ Skip vote
                <span className="text-xs text-slate-400 ml-2">(don't eliminate anyone)</span>
              </span>
              <div className="flex items-center gap-3 shrink-0">
                {skipVoters.length > 0 && (
                  <span className="text-xs text-slate-400 italic hidden sm:block">
                    ← {skipVoters.join(', ')}
                  </span>
                )}
                {skipVotes > 0 && (
                  <span className={`text-sm font-bold px-2 py-0.5 rounded ${skipVotes >= 2 ? 'text-amber-300 bg-amber-950/60' : 'text-slate-300 bg-slate-700'}`}>
                    {skipVotes}
                  </span>
                )}
              </div>
            </div>
          )}

          {isVoting && isAlive && myVoteTargetId === SKIP_VOTE && (
            <p className="text-sm text-amber-400 mt-3">
              Your vote: <span className="font-semibold">Skip</span>
              <span className="text-slate-500 ml-1">(click another to change)</span>
            </p>
          )}
          {isVoting && isAlive && myVoteTarget && (
            <p className="text-sm text-red-400 mt-3">
              Your vote: <span className="font-semibold">{myVoteTarget.name}</span>
              <span className="text-slate-500 ml-1">(click another to change)</span>
            </p>
          )}
          {isVoting && isAlive && !myVoteTargetId && (
            <p className="text-sm text-slate-400 mt-3">Click a player to vote for elimination, or skip.</p>
          )}
        </div>
      </div>

      <div className="w-full lg:w-80 bg-slate-900 border border-slate-700 rounded-xl flex flex-col" style={{ height: '480px' }}>
        <div className="p-3 border-b border-slate-700">
          <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide">Village chat</p>
        </div>
        <div className="flex-1 min-h-0">
          <Chat
            messages={dayMessages}
            onSend={content => socket.emit('chat:send', content)}
            canSend={isAlive && !isVoting && state.phase !== 'day_result' && (isArena ? isSpeaker : true) && !state.labelCheckpoint}
            placeholder={
              isVoting
                ? 'Voting in progress'
                : state.phase === 'day_result'
                  ? 'Voting completed'
                  : isArena
                    ? (isSpeaker ? 'Your one message…' : 'Wait for your bid-to-speak turn')
                    : 'Discuss with the village…'
            }
          />
        </div>
      </div>
    </div>
  )
}
