'use client'

import { useState, useEffect } from 'react'
import type { ClientGameState, ChatMessage } from '@/types/game'
import type { GameSocket } from '@/app/room/[code]/page'
import Button from '@/components/ui/Button'
import PlayerList from './PlayerList'
import Chat from './Chat'

interface Props {
  state: ClientGameState
  socket: GameSocket
  messages: ChatMessage[]
}

export default function MayorElection({ state, socket, messages }: Props) {
  const [selected, setSelected] = useState<string | null>(null)
  const [submitted, setSubmitted] = useState(false)
  const [timeLeft, setTimeLeft] = useState<number | null>(null)

  const me = state.players.find(p => p.id === state.myId)
  const isAlive = me?.isAlive ?? false
  const alivePlayers = state.players.filter(p => p.isAlive)
  const hasVoted = state.mayorVotes[state.myId] !== undefined
  const dayMessages = messages.filter(m => m.phase !== 'night')

  useEffect(() => {
    if (!state.phaseEndTime) return
    const tick = () => {
      const remaining = Math.max(0, state.phaseEndTime! - Date.now())
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

  const voteCount = Object.keys(state.mayorVotes).length

  return (
    <div className="flex flex-col lg:flex-row gap-4 h-full p-4 max-w-5xl mx-auto w-full">
      <div className="flex-1 flex flex-col gap-4 min-w-0">
        <div className="text-center bg-slate-900 border border-violet-800/50 rounded-xl p-4">
          <div className="text-4xl mb-2">👑</div>
          <h2 className="text-xl font-bold text-slate-100">Mayor Election</h2>
          <p className="text-slate-400 text-sm mt-1">
            Vote for a player to become Mayor. The Mayor's vote counts double during day votes.
          </p>
          {timeLeft !== null && (
            <p className={`text-lg font-mono font-bold mt-2 ${timeLeft <= 10 ? 'text-red-400' : 'text-violet-400'}`}>
              {timeLeft}s
            </p>
          )}
        </div>

        <div className="bg-slate-900 border border-violet-800/50 rounded-xl p-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold text-slate-300 uppercase tracking-wide">Players</h3>
            <span className="text-xs text-slate-400">{voteCount}/{alivePlayers.length} voted</span>
          </div>
          {isAlive && !hasVoted && !submitted ? (
            <PlayerList
              players={alivePlayers}
              myId={state.myId}
              onSelect={setSelected}
              selectedId={selected ?? undefined}
              selectable
            />
          ) : (
            <PlayerList
              players={alivePlayers}
              myId={state.myId}
            />
          )}
        </div>

        {isAlive && !hasVoted && !submitted && (
          <Button
            className="w-full"
            variant="primary"
            disabled={!selected}
            onClick={handleVote}
          >
            Vote for Mayor
          </Button>
        )}

        {(hasVoted || submitted) && (
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
            canSend={isAlive}
            placeholder="Discuss your pick for Mayor…"
          />
        </div>
      </div>
    </div>
  )
}
