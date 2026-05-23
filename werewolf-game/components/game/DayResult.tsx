'use client'

import { useEffect, useState } from 'react'
import type { ClientGameState } from '@/types/game'
import type { GameSocket } from '@/app/room/[code]/page'
import Button from '@/components/ui/Button'

interface Props {
  state: ClientGameState
  socket: GameSocket
}

export default function DayResult({ state, socket }: Props) {
  const me = state.players.find(p => p.id === state.myId)
  const isHost = me?.isHost
  const [remaining, setRemaining] = useState(0)

  useEffect(() => {
    if (!state.phaseEndTime) return
    const tick = () => setRemaining(Math.max(0, Math.ceil((state.phaseEndTime! - Date.now()) / 1000)))
    tick()
    const id = setInterval(tick, 250)
    return () => clearInterval(id)
  }, [state.phaseEndTime])

  const outcome = state.dayVoteOutcome
  const victim = state.lastEliminated

  let icon = '🌑'
  let headline = ''
  let body: React.ReactNode = null
  let tone = 'border-slate-700 bg-slate-900'

  if (outcome === 'eliminated' && victim) {
    icon = '⚖️'
    headline = `${victim.playerName} has been eliminated`
    body = (
      <p className="text-slate-300 mt-2 text-sm">
        They were a <span className="font-semibold capitalize text-slate-100">{victim.role}</span>.
      </p>
    )
    tone = 'border-red-800 bg-red-950/40'
  } else if (outcome === 'skipped') {
    icon = '⏭'
    headline = 'The village chose to skip'
    body = <p className="text-slate-300 mt-2 text-sm">No one was eliminated today.</p>
    tone = 'border-amber-800 bg-amber-950/40'
  } else if (outcome === 'tie') {
    icon = '⚖️'
    headline = 'The vote was tied'
    body = <p className="text-slate-300 mt-2 text-sm">No one was eliminated today.</p>
    tone = 'border-slate-700 bg-slate-800/60'
  }

  return (
    <div className="flex-1 flex items-center justify-center p-6">
      <div className={`max-w-md w-full border rounded-2xl p-8 text-center ${tone}`}>
        <div className="text-6xl mb-3">{icon}</div>
        <h2 className="text-xl font-bold text-slate-100">{headline}</h2>
        {body}

        <div className="mt-6 border-t border-slate-700 pt-4">
          <p className="text-xs text-slate-500 uppercase tracking-wide">Night falls in</p>
          <p className="text-2xl font-mono text-slate-300 mt-1">{remaining}s</p>
        </div>

        {isHost && (
          <div className="mt-4">
            <Button size="sm" variant="ghost" onClick={() => socket.emit('phase:advance')}>
              Continue now
            </Button>
          </div>
        )}
      </div>
    </div>
  )
}
