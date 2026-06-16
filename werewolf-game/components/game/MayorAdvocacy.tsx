'use client'

import { useEffect, useRef, useState } from 'react'
import type { ClientGameState, ChatMessage } from '@/types/game'
import type { GameSocket } from '@/app/room/[code]/page'
import Chat from './Chat'
import PlayerName from './PlayerName'
import { play } from '@/lib/sounds'
import { safeDateNow } from '@/lib/clock'

interface Props {
  state: ClientGameState
  socket: GameSocket
  messages: ChatMessage[]
}

function useSecondsLeft(endTime: number | null): number {
  const [s, setS] = useState(0)
  useEffect(() => {
    if (!endTime) { setS(0); return }
    const tick = () => setS(Math.max(0, Math.ceil((endTime - safeDateNow()) / 1000)))
    tick()
    const id = setInterval(tick, 250)
    return () => clearInterval(id)
  }, [endTime])
  return s
}

export default function MayorAdvocacy({ state, socket, messages }: Props) {
  const a = state.advocacy
  const me = state.players.find(p => p.id === state.myId)
  const isAlive = me?.isAlive ?? false
  const left = useSecondsLeft(a?.endTime ?? null)
  const dayMessages = messages.filter(m => m.phase !== 'night' || m.isSystem)
  const isHost = me?.isHost

  const isMyAdvocacyTurn = !!a?.active && !!a.myTurn && isAlive
  const advocacyTurnRef = useRef(false)
  useEffect(() => {
    if (isMyAdvocacyTurn && !advocacyTurnRef.current) play('your-turn')
    advocacyTurnRef.current = isMyAdvocacyTurn
  }, [isMyAdvocacyTurn])

  if (!a?.active) return null
  const currentName = state.players.find(p => p.id === a.currentSpeakerId)?.name ?? '?'
  const canSend = isAlive && a.myTurn
  const myPos = a.order.indexOf(state.myId)

  return (
    <div className="flex flex-col lg:flex-row gap-4 h-full p-4 max-w-5xl mx-auto w-full">
      <div className="flex-1 flex flex-col gap-4 min-w-0">
        <div className="text-center bg-slate-900 border border-violet-800/50 rounded-xl p-4">
          <div className="text-4xl mb-2">👑</div>
          <h2 className="text-xl font-bold text-slate-100">Mayor Election — Advocacy</h2>
          <p className="text-slate-400 text-sm mt-1">
            Each player makes one statement in turn. Send a single message when it&rsquo;s your turn.
          </p>
          {a.endTime !== null && (
            <p className={`text-lg font-mono font-bold mt-2 ${left <= 5 ? 'text-red-400' : 'text-violet-400'}`}>
              {left}s
            </p>
          )}
          {isHost && (
            <button
              onClick={() => socket.emit('phase:advance')}
              className="mt-3 text-xs px-3 py-1 bg-slate-800 hover:bg-slate-700 border border-slate-600 rounded transition-colors cursor-pointer text-slate-300"
            >
              Skip current speaker
            </button>
          )}
        </div>

        <div className="bg-slate-900 border border-slate-700 rounded-xl p-4">
          <p className="text-xs uppercase tracking-wide text-slate-400 font-semibold mb-2">Order</p>
          <ul className="space-y-1">
            {a.order.map((id, i) => {
              const p = state.players.find(x => x.id === id)
              const done = i < a.turn
              const current = i === a.turn
              return (
                <li
                  key={id}
                  className={`text-sm flex items-center gap-2 ${
                    done ? 'text-slate-500' : current ? 'text-violet-300 font-semibold' : 'text-slate-300'
                  }`}
                >
                  <span className="font-mono w-5 text-xs">{i + 1}.</span>
                  <span>
                    <PlayerName name={p?.name ?? '?'} role={p?.role} isMe={p?.id === state.myId} showTeammateIcon={false} />
                  </span>
                  {done && <span className="text-xs">✓</span>}
                  {current && <span className="text-xs">← now</span>}
                </li>
              )
            })}
          </ul>
        </div>

        {a.myTurn && isAlive && (
          <div className="bg-slate-900 border border-violet-800/60 rounded-xl p-4 text-center">
            <p className="text-sm text-violet-200 font-semibold">Your turn — send one message to advocate for yourself.</p>
          </div>
        )}
        {!a.myTurn && (
          <div className="bg-slate-900 border border-slate-700 rounded-xl p-4 text-center">
            <p className="text-sm text-slate-300">
              <span className="font-semibold">
                <PlayerName name={currentName} role={state.players.find(p => p.id === a.currentSpeakerId)?.role} showTeammateIcon={false} />
              </span> is speaking…
            </p>
            {myPos > a.turn && isAlive && (
              <p className="text-xs text-slate-500 mt-1">You&rsquo;ll be up at position {myPos + 1}.</p>
            )}
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
            canSend={canSend}
            placeholder={canSend ? 'Make your case…' : 'Wait for your turn'}
          />
        </div>
      </div>
    </div>
  )
}
