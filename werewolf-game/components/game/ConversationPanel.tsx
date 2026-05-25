'use client'

import { useEffect, useRef, useState } from 'react'
import type { ClientGameState } from '@/types/game'
import type { GameSocket } from '@/app/room/[code]/page'
import { play } from '@/lib/sounds'

interface Props {
  state: ClientGameState
  socket: GameSocket
}

function useSecondsLeft(endTime: number | null): number {
  const [s, setS] = useState(0)
  useEffect(() => {
    if (!endTime) { setS(0); return }
    const tick = () => setS(Math.max(0, Math.ceil((endTime - Date.now()) / 1000)))
    tick()
    const id = setInterval(tick, 250)
    return () => clearInterval(id)
  }, [endTime])
  return s
}

export default function ConversationPanel({ state, socket }: Props) {
  const c = state.conversation
  const me = state.players.find(p => p.id === state.myId)
  const isAlive = me?.isAlive ?? false
  const alive = state.players.filter(p => p.isAlive)
  const bidLeft = useSecondsLeft(c?.bidEndTime ?? null)
  const speakLeft = useSecondsLeft(c?.speakerEndTime ?? null)

  const isMySpeakerTurn = !!c?.active && c.sub === 'speak' && c.speakerId === state.myId && isAlive
  const speakerTurnRef = useRef(false)
  useEffect(() => {
    if (isMySpeakerTurn && !speakerTurnRef.current) play('your-turn')
    speakerTurnRef.current = isMySpeakerTurn
  }, [isMySpeakerTurn])

  if (!c?.active) return null

  const inBid = c.sub === 'bid'
  const inSpeak = c.sub === 'speak'
  const queue = c.pendingSpeakers ?? []
  const queueNames = queue.map(id => state.players.find(p => p.id === id)?.name ?? '?')
  const myQueuePos = queue.indexOf(state.myId)

  return (
    <div className="bg-slate-900 border border-slate-700 rounded-xl p-4 flex flex-col gap-3">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div>
          <p className="text-xs uppercase tracking-wide text-slate-400 font-semibold">
            {c.context === 'mayor' ? 'Mayor discussion' : 'Day discussion'}
          </p>
          <p className="text-sm text-slate-200">
            Round {c.round} of {c.maxRounds} —{' '}
            {inBid ? <span className="text-amber-300 font-semibold">Bid to speak</span> : <span className="text-violet-300 font-semibold">Speaking</span>}
          </p>
        </div>
        {(inBid && c.bidEndTime) && (
          <span className={`text-base font-mono px-2 py-0.5 rounded ${bidLeft <= 3 ? 'text-red-300 bg-red-950/40' : 'text-amber-300 bg-amber-950/40'}`}>
            {bidLeft}s
          </span>
        )}
        {(inSpeak && c.speakerEndTime) && (
          <span className={`text-base font-mono px-2 py-0.5 rounded ${speakLeft <= 5 ? 'text-red-300 bg-red-950/40' : 'text-violet-300 bg-violet-950/40'}`}>
            {speakLeft}s
          </span>
        )}
      </div>

      {queue.length > 0 && (
        <div className="text-xs bg-violet-950/30 border border-violet-800/60 rounded-lg p-2">
          <span className="text-violet-300 font-semibold">Up next (mentioned):</span>{' '}
          <span className="text-slate-200">{queueNames.join(' → ')}</span>
          {myQueuePos >= 0 && isAlive && (
            <span className="text-violet-200"> · you&rsquo;re #{myQueuePos + 1} — no bid needed</span>
          )}
        </div>
      )}

      {inBid && (
        <div>
          <p className="text-xs text-slate-400 mb-2">
            Privately pick how much you want to speak this round. Highest bid wins; ties broken randomly.
          </p>
          {isAlive ? (
            <div className="grid grid-cols-5 gap-2">
              {[1, 2, 3, 4, 5].map(n => (
                <button
                  key={n}
                  onClick={() => socket.emit('conversation:bid', n)}
                  className={`py-2 rounded-lg border text-sm font-semibold transition-colors cursor-pointer ${
                    c.myBid === n
                      ? 'border-amber-500 bg-amber-950/60 text-amber-200'
                      : 'border-slate-700 bg-slate-800/60 text-slate-300 hover:border-amber-700'
                  }`}
                >
                  {n}
                </button>
              ))}
            </div>
          ) : (
            <p className="text-xs text-slate-500 italic">Dead players don&rsquo;t bid.</p>
          )}
          <p className="text-xs text-slate-500 mt-2">
            {c.bidsSubmittedCount}/{alive.length} bids in
            {c.myBid !== null && isAlive && <> · your bid: <span className="text-amber-300 font-semibold">{c.myBid}</span></>}
          </p>
        </div>
      )}

      {inSpeak && (
        <div className="bg-slate-800/40 border border-violet-800/60 rounded-lg p-3">
          {c.speakerId === state.myId ? (
            <p className="text-sm text-violet-200">
              <span className="font-bold">Your turn to speak.</span> Send one message in the chat — the round will advance as soon as you do.
            </p>
          ) : (
            <p className="text-sm text-slate-300">
              <span className="font-semibold text-violet-300">{c.speakerName}</span> is speaking…
            </p>
          )}
        </div>
      )}

      {c.history.length > 0 && (
        <details className="text-xs text-slate-400">
          <summary className="cursor-pointer hover:text-slate-200">Past rounds</summary>
          <ul className="mt-2 space-y-1">
            {c.history.map(h => (
              <li key={h.round}>Round {h.round}: <span className="text-slate-300">{h.speakerName}</span></li>
            ))}
          </ul>
        </details>
      )}
    </div>
  )
}
