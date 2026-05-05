'use client'

import { useState, useEffect } from 'react'
import type { ClientGameState } from '@/types/game'
import type { GameSocket } from '@/app/room/[code]/page'
import Button from '@/components/ui/Button'
import PlayerList from './PlayerList'

interface Props {
  state: ClientGameState
  socket: GameSocket
}

export default function MayorElection({ state, socket }: Props) {
  const [selected, setSelected] = useState<string | null>(null)
  const [submitted, setSubmitted] = useState(false)
  const [timeLeft, setTimeLeft] = useState<number | null>(null)

  const me = state.players.find(p => p.id === state.myId)
  const isAlive = me?.isAlive ?? false
  const alivePlayers = state.players.filter(p => p.isAlive)
  const hasVoted = state.mayorVotes[state.myId] !== undefined

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
    <div className="flex flex-col items-center gap-6 py-8 px-4 max-w-lg mx-auto w-full">
      <div className="text-center">
        <div className="text-5xl mb-3">👑</div>
        <h2 className="text-2xl font-bold text-slate-100">Mayor Election</h2>
        <p className="text-slate-400 text-sm mt-1">
          Vote for a player to become Mayor. The Mayor's vote counts double during day votes.
        </p>
        {timeLeft !== null && (
          <p className={`text-lg font-mono font-bold mt-2 ${timeLeft <= 10 ? 'text-red-400' : 'text-violet-400'}`}>
            {timeLeft}s
          </p>
        )}
      </div>

      <div className="w-full bg-slate-900 border border-violet-800/50 rounded-xl p-4">
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
  )
}
