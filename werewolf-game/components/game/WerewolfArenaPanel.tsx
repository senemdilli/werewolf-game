'use client'

import { useState } from 'react'
import type { ClientGameState } from '@/types/game'
import { WOLF_VOTE_NOBODY } from '@/types/game'
import type { GameSocket } from '@/app/room/[code]/page'
import Button from '@/components/ui/Button'

interface Props {
  state: ClientGameState
  socket: GameSocket
}

export default function WerewolfArenaPanel({ state, socket }: Props) {
  const arena = state.wolfArena
  const [selected, setSelected] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  if (!arena) return null

  const me = state.players.find(p => p.id === state.myId)
  const alivePlayers = state.players.filter(p => p.isAlive)
  const targetable = alivePlayers.filter(p => p.id !== state.myId && !state.werewolfTeammates?.includes(p.id))
  const playerName = (id: string) =>
    id === WOLF_VOTE_NOBODY ? 'Spare everyone' : state.players.find(p => p.id === id)?.name ?? '?'

  const currentVoter = arena.order[arena.turn]
  const currentVoterName = state.players.find(p => p.id === currentVoter)?.name ?? '?'
  const isMyTurn = arena.myTurn && !!me?.isAlive

  function handleVote() {
    if (!selected || submitting) return
    setSubmitting(true)
    socket.emit('night:werewolf_vote', selected)
    setTimeout(() => setSubmitting(false), 2000)
  }

  return (
    <div className="bg-slate-900 border border-red-900 rounded-xl p-4 flex flex-col gap-4">
      <div>
        <p className="text-sm font-semibold text-red-300">
          🐺 Wolf Pack Vote — Round {arena.round} of 3
        </p>
        <p className="text-xs text-slate-400 mt-1">
          Sequential voting, no talking. After round 3, all wolves must agree on the same target — otherwise no one dies.
        </p>
      </div>

      {/* Turn order */}
      <div>
        <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-2">Speaking order this night</p>
        <div className="flex flex-wrap gap-2 text-xs">
          {arena.order.map((wolfId, i) => {
            const name = state.players.find(p => p.id === wolfId)?.name ?? '?'
            const voted = !!arena.currentVotes[wolfId]
            const isCurrent = !arena.resolved && i === arena.turn
            return (
              <span
                key={wolfId}
                className={`px-2 py-1 rounded border ${
                  isCurrent
                    ? 'border-red-500 bg-red-950/60 text-red-200 font-semibold'
                    : voted
                    ? 'border-emerald-800 bg-emerald-950/40 text-emerald-300'
                    : 'border-slate-700 bg-slate-800/40 text-slate-400'
                }`}
              >
                {i + 1}. {name}{voted ? ' ✓' : isCurrent ? ' …' : ''}
              </span>
            )
          })}
        </div>
      </div>

      {/* History */}
      {arena.history.length > 0 && (
        <div>
          <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-2">Previous rounds</p>
          <div className="space-y-2 text-xs">
            {arena.history.map(h => (
              <div key={h.round} className="bg-slate-800/60 border border-slate-700 rounded-lg p-2">
                <p className="text-slate-400 font-semibold mb-1">Round {h.round}</p>
                {Object.entries(h.votes).map(([voter, target]) => (
                  <p key={voter} className="text-slate-300">
                    {state.players.find(p => p.id === voter)?.name ?? '?'} → <span className="text-red-300">{playerName(target)}</span>
                  </p>
                ))}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Current round live votes */}
      {!arena.resolved && Object.keys(arena.currentVotes).length > 0 && (
        <div>
          <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-2">Round {arena.round} so far</p>
          <div className="space-y-1 text-xs">
            {Object.entries(arena.currentVotes).map(([voter, target]) => (
              <p key={voter} className="text-slate-300">
                {state.players.find(p => p.id === voter)?.name ?? '?'} → <span className="text-red-300">{playerName(target)}</span>
              </p>
            ))}
          </div>
        </div>
      )}

      {/* Resolved state */}
      {arena.resolved && (
        <div className="bg-slate-800/60 border border-slate-700 rounded-lg p-3 text-sm text-slate-300">
          The wolves have decided. Waiting for the rest of the night to play out…
        </div>
      )}

      {/* Action */}
      {!arena.resolved && isMyTurn && (
        <div className="bg-slate-800/60 border border-red-800 rounded-lg p-3 flex flex-col gap-3">
          <p className="text-sm font-semibold text-red-300">Your turn — pick a target</p>
          <div className="grid grid-cols-2 gap-2">
            {targetable.map(p => (
              <button
                key={p.id}
                onClick={() => setSelected(p.id)}
                className={`text-sm px-3 py-2 rounded-lg border transition-colors text-left cursor-pointer ${
                  selected === p.id
                    ? 'border-red-500 bg-red-950/60 text-red-100'
                    : 'border-slate-700 bg-slate-900 text-slate-300 hover:border-red-700'
                }`}
              >
                {p.name}
              </button>
            ))}
            <button
              onClick={() => setSelected(WOLF_VOTE_NOBODY)}
              className={`text-sm px-3 py-2 rounded-lg border transition-colors text-left cursor-pointer col-span-2 ${
                selected === WOLF_VOTE_NOBODY
                  ? 'border-amber-500 bg-amber-950/60 text-amber-100'
                  : 'border-slate-700 bg-slate-900 text-slate-300 hover:border-amber-700'
              }`}
            >
              🕊 Spare everyone (vote &ldquo;nobody&rdquo;)
            </button>
          </div>
          <Button
            disabled={!selected || submitting}
            loading={submitting}
            onClick={handleVote}
            variant="danger"
            className="w-full"
          >
            Confirm vote
          </Button>
        </div>
      )}

      {!arena.resolved && !isMyTurn && (
        <div className="bg-slate-800/60 border border-slate-700 rounded-lg p-3 text-sm text-slate-300">
          Waiting for <span className="font-semibold text-red-300">{currentVoterName}</span> to vote…
        </div>
      )}
    </div>
  )
}
