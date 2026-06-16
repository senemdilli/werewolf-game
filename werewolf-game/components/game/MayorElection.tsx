'use client'

import { useState, useEffect } from 'react'
import type { ClientGameState, ChatMessage } from '@/types/game'
import type { GameSocket } from '@/app/room/[code]/page'
import Button from '@/components/ui/Button'
import PlayerList from './PlayerList'
import PlayerName from './PlayerName'
import Chat from './Chat'
import ConversationPanel from './ConversationPanel'
import { safeDateNow } from '@/lib/clock'

interface Props {
  state: ClientGameState
  socket: GameSocket
  messages: ChatMessage[]
}

export default function MayorElection({ state, socket, messages }: Props) {
  const [selected, setSelected] = useState<string | null>(null)
  const [submitted, setSubmitted] = useState(false)
  const [runoffSelected, setRunoffSelected] = useState<string | null>(null)
  const [timeLeft, setTimeLeft] = useState<number | null>(null)

  const me = state.players.find(p => p.id === state.myId)
  const isAlive = me?.isAlive ?? false
  const alivePlayers = state.players.filter(p => p.isAlive)
  const hasVoted = state.mayorVotes[state.myId] !== undefined
  const dayMessages = messages.filter(m => m.phase !== 'night' || m.isSystem)
  const isArena = state.gameMode === 'arena'
  const inConversation = !!state.conversation?.active
  const inRunoff = !!state.mayorRunoff?.active
  const inVote = !inConversation && !inRunoff
  const isSpeaker = state.conversation?.sub === 'speak' && state.conversation.speakerId === state.myId
  const allowSelfVote = isArena

  useEffect(() => {
    if (!state.phaseEndTime) { setTimeLeft(null); return }
    const tick = () => {
      const remaining = Math.max(0, state.phaseEndTime! - safeDateNow())
      setTimeLeft(Math.ceil(remaining / 1000))
    }
    tick()
    const id = setInterval(tick, 500)
    return () => clearInterval(id)
  }, [state.phaseEndTime])

  function handleVote() {
    if (!selected) return
    setSubmitted(true)
    socket.emit('mayor:vote', selected)
  }

  function handleRunoffVote() {
    if (!runoffSelected) return
    socket.emit('mayor:runoff_vote', runoffSelected)
  }

  const voteCount = Object.keys(state.mayorVotes).length
  const runoffVoteCount = Object.keys(state.mayorRunoff?.candidates ?? []).length // placeholder
  void runoffVoteCount

  return (
    <div className="flex flex-col lg:flex-row gap-4 h-full p-4 max-w-5xl mx-auto w-full">
      <div className="flex-1 flex flex-col gap-4 min-w-0">
        <div className="text-center bg-slate-900 border border-violet-800/50 rounded-xl p-4">
          <div className="text-4xl mb-2">👑</div>
          <h2 className="text-xl font-bold text-slate-100">Mayor Election</h2>
          <p className="text-slate-400 text-sm mt-1">
            {isArena
              ? inConversation
                ? 'Bid each round to earn a chance to speak.'
                : inRunoff
                  ? 'Top candidates tied. Vote again to break the tie.'
                  : 'Vote for a player to become Mayor. The Mayor breaks ties in day votes.'
              : 'Vote for a player to become Mayor. The Mayor’s vote counts double during day votes.'}
          </p>
          {inVote && timeLeft !== null && (
            <p className={`text-lg font-mono font-bold mt-2 ${timeLeft <= 10 ? 'text-red-400' : 'text-violet-400'}`}>
              {timeLeft}s
            </p>
          )}
        </div>

        {isArena && inConversation && (
          <ConversationPanel state={state} socket={socket} />
        )}

        {isArena && inRunoff && state.mayorRunoff && (
          <div className="bg-slate-900 border border-amber-800/60 rounded-xl p-4 flex flex-col gap-3">
            <p className="text-sm font-semibold text-amber-200">Runoff — pick one</p>
            <div className="grid grid-cols-1 gap-2">
              {state.mayorRunoff.candidates.map(id => {
                const p = state.players.find(x => x.id === id)
                if (!p) return null
                const isSelected = (runoffSelected ?? state.mayorRunoff!.myVote) === id
                return (
                  <button
                    key={id}
                    onClick={() => isAlive && setRunoffSelected(id)}
                    disabled={!isAlive}
                    className={`text-left px-3 py-2 rounded-lg border transition-colors cursor-pointer ${
                      isSelected
                        ? 'border-amber-500 bg-amber-950/60 text-amber-200'
                        : 'border-slate-700 bg-slate-800/60 text-slate-300 hover:border-amber-600'
                    }`}
                  >
                    <PlayerName name={p.name} role={p.role} showTeammateIcon={false} />
                  </button>
                )
              })}
            </div>
            <Button
              className="w-full"
              variant="primary"
              disabled={!runoffSelected || !isAlive}
              onClick={handleRunoffVote}
            >
              Confirm runoff vote
            </Button>
            {state.mayorRunoff.myVote && (
              <p className="text-xs text-slate-400 text-center">
                Your runoff vote:{' '}
                <PlayerName
                  name={state.players.find(p => p.id === state.mayorRunoff!.myVote)?.name ?? '?'}
                  role={state.players.find(p => p.id === state.mayorRunoff!.myVote)?.role}
                  showTeammateIcon={false}
                />
              </p>
            )}
          </div>
        )}

        {inVote && (
          <div className="bg-slate-900 border border-violet-800/50 rounded-xl p-4">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-semibold text-slate-300 uppercase tracking-wide">Players</h3>
              <span className="text-xs text-slate-400">{voteCount}/{alivePlayers.length} voted</span>
            </div>
            {/* Show all players (dead included, with revealed roles) for context.
                PlayerList only makes alive non-self entries selectable. */}
            {isAlive && !hasVoted && !submitted ? (
              <PlayerList
                players={state.players}
                myId={state.myId}
                onSelect={setSelected}
                selectedId={selected ?? undefined}
                selectable
                excludeId={allowSelfVote ? undefined : state.myId}
              />
            ) : (
              <PlayerList
                players={state.players}
                myId={state.myId}
              />
            )}
          </div>
        )}

        {inVote && isAlive && !hasVoted && !submitted && (
          <Button
            className="w-full"
            variant="primary"
            disabled={!selected}
            onClick={handleVote}
          >
            Vote for Mayor
          </Button>
        )}

        {inVote && (hasVoted || submitted) && (
          <div className="bg-slate-900 border border-emerald-800 rounded-xl p-4 text-center w-full">
            <p className="text-emerald-400 text-sm">✓ Vote submitted. Waiting for others…</p>
          </div>
        )}

        {!isAlive && (
          <div className="bg-slate-900 border border-slate-700 rounded-xl p-4 text-center w-full">
            <p className="text-slate-400 text-sm">You are dead and cannot vote.</p>
          </div>
        )}
      </div>

      <div className="w-full lg:w-80 bg-slate-900 border border-slate-700 rounded-xl flex flex-col" style={{ height: '480px' }}>
        <div className="p-3 border-b border-slate-700">
          <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide">Village chat</p>
        </div>
        <div className="flex-1 min-h-0">
          <Chat
            messages={dayMessages}
            onSend={content => socket.emit('chat:send', content)}
            canSend={isAlive && (
              isArena
                ? (inConversation && isSpeaker)
                : true
            )}
            placeholder={
              isArena
                ? inConversation
                  ? isSpeaker ? 'Your one message…' : 'Wait for your turn to speak'
                  : 'Chat closed during voting'
                : 'Discuss your pick for Mayor…'
            }
          />
        </div>
      </div>
    </div>
  )
}
