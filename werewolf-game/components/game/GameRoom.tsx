'use client'

import { useEffect, useState, useCallback, useRef } from 'react'
import { useRouter } from 'next/navigation'
import { connectSocket, disconnectSocket } from '@/lib/socket-client'
import type { ClientGameState, ChatMessage, SeerResult } from '@/types/game'
import type { GameSocket } from '@/app/room/[code]/page'
import Lobby from './Lobby'
import RoleReveal from './RoleReveal'
import NightPhase from './NightPhase'
import MayorElection from './MayorElection'
import MayorAdvocacy from './MayorAdvocacy'
import DayPhase from './DayPhase'
import DayResult from './DayResult'
import GameOver from './GameOver'
import NotePanel from './NotePanel'
import LabelPanel from './LabelPanel'
import MuteToggle from './MuteToggle'
import { play } from '@/lib/sounds'

const LABELABLE_PHASES = new Set([
  'mayor_advocacy', 'mayor_election', 'day_discussion', 'day_vote', 'day_result',
])

function LabelingBreakBanner({ endTime }: { endTime: number }) {
  const [left, setLeft] = useState(Math.max(0, Math.ceil((endTime - Date.now()) / 1000)))
  useEffect(() => {
    const tick = () => setLeft(Math.max(0, Math.ceil((endTime - Date.now()) / 1000)))
    tick()
    const id = setInterval(tick, 250)
    return () => clearInterval(id)
  }, [endTime])
  return (
    <div className="fixed top-4 left-1/2 -translate-x-1/2 z-50 bg-amber-950 border border-amber-700 text-amber-100 px-4 py-2 rounded-lg text-sm shadow-lg flex items-center gap-3">
      <span className="font-semibold">🏷️ Labeling break</span>
      <span className="text-amber-200">
        Phase deadline paused — <span className="font-mono">{left}s</span> remaining
      </span>
    </div>
  )
}

interface Props {
  roomCode: string
  playerId: string
}

export default function GameRoom({ roomCode, playerId }: Props) {
  const router = useRouter()
  const [socket, setSocket] = useState<GameSocket | null>(null)
  const [state, setState] = useState<ClientGameState | null>(null)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [seerResults, setSeerResults] = useState<(SeerResult & { id: string; endTime: number })[]>([])
  const [acknowledged, setAcknowledged] = useState(false)
  const [starting, setStarting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [labelAutoOpenTrigger, setLabelAutoOpenTrigger] = useState<string | null>(null)
  const lastProcessedSystemMsgRef = useRef<string | null>(null)
  const prevPhaseRef = useRef<string | null>(null)
  const lastCuedMsgIdRef = useRef<string | null>(null)

  useEffect(() => {
    const s = connectSocket() as GameSocket
    setSocket(s)

    s.on('game:state', (newState) => {
      setState(newState)
      if (newState.phase === 'lobby') setSeerResults([])
      if (newState.phase !== 'role_reveal') setAcknowledged(false)
      if (newState.phase !== 'lobby' && newState.phase !== 'game_over') setStarting(false)
    })

    s.on('chat:message', (msg) => {
      setMessages(prev => [...prev, msg])
    })

    s.on('seer:result', (result) => {
      const id = `${Date.now()}-${Math.random()}`
      const endTime = Date.now() + 10000
      setSeerResults(prev => [...prev, { ...result, id, endTime }])
      setTimeout(() => {
        setSeerResults(prev => prev.filter(item => item.id !== id))
      }, 10000)
    })

    s.on('error', (msg) => {
      setError(msg)
      setTimeout(() => setError(null), 4000)
    })

    s.on('room:kicked', (reason) => {
      // Host removed us from the lobby. Clear our session and bounce home with
      // a message that survives the navigation via sessionStorage.
      sessionStorage.removeItem('ww_playerId')
      sessionStorage.removeItem('ww_roomCode')
      sessionStorage.setItem('ww_lastError', reason)
      disconnectSocket()
      router.push('/')
    })

    s.emit('room:rejoin', { roomCode, playerId }, ({ success, error }) => {
      if (!success) {
        setError(error || 'Failed to rejoin room')
      }
    })

    return () => {
      s.off('game:state')
      s.off('chat:message')
      s.off('seer:result')
      s.off('error')
      s.off('room:kicked')
    }
  }, [roomCode, playerId])

  // Auto-open the Labels panel when a new daytime system announcement arrives
  // during a labelable phase. Track the last-seen system message so we don't
  // re-trigger on re-renders.
  useEffect(() => {
    if (!state || !LABELABLE_PHASES.has(state.phase)) return
    for (let i = messages.length - 1; i >= 0; i--) {
      const m = messages[i]
      if (!m.isSystem || !LABELABLE_PHASES.has(m.phase)) continue
      if (m.id === lastProcessedSystemMsgRef.current) return
      lastProcessedSystemMsgRef.current = m.id
      setLabelAutoOpenTrigger(m.id)
      return
    }
  }, [messages, state])

  // Phase-transition audio cues. Fires once per phase change (not on every render).
  useEffect(() => {
    if (!state) return
    const prev = prevPhaseRef.current
    const cur = state.phase
    if (prev === cur) return
    prevPhaseRef.current = cur
    if (!prev) return  // first paint — no cue for "joining a room"
    switch (cur) {
      case 'night':            play('phase-night'); break
      case 'mayor_advocacy':
      case 'day_discussion':   play('phase-day'); break
      case 'day_vote':
      case 'mayor_election':   play('vote-open'); break
      case 'day_result':       play('vote-result'); break
    }
  }, [state])

  // Chat-arrival cues: 'dawn' for the morning system message, otherwise a
  // (rate-limited) ping for non-system, non-own messages.
  useEffect(() => {
    if (messages.length === 0) return
    const m = messages[messages.length - 1]
    if (m.id === lastCuedMsgIdRef.current) return
    lastCuedMsgIdRef.current = m.id
    if (m.isSystem) {
      if (m.content.startsWith('Dawn breaks')) play('dawn')
      return
    }
    if (m.playerId && m.playerId !== playerId) play('chat-msg')
  }, [messages, playerId])

  const handleStart = useCallback(() => {
    if (!socket) return
    setStarting(true)
    socket.emit('game:start', ({ success, error }) => {
      if (!success) {
        setError(error || 'Failed to start')
        setStarting(false)
      }
    })
  }, [socket])

  const handleReady = useCallback(() => {
    if (!socket) return
    socket.emit('room:ready')
  }, [socket])

  const handleAcknowledge = useCallback(() => {
    if (!socket) return
    setAcknowledged(true)
    socket.emit('game:acknowledge_role')
  }, [socket])

  const handlePlayAgain = useCallback(() => {
    disconnectSocket()
    sessionStorage.removeItem('ww_playerId')
    sessionStorage.removeItem('ww_roomCode')
    router.push('/')
  }, [router])

  if (!state) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <p className="text-slate-400 animate-pulse">Connecting…</p>
      </div>
    )
  }

  return (
    <div className="min-h-screen flex flex-col">
      <div className="fixed top-3 left-3 z-40">
        <MuteToggle />
      </div>

      {error && (
        <div className="fixed top-4 left-1/2 -translate-x-1/2 z-50 bg-red-900 border border-red-700 text-red-100 px-4 py-2 rounded-lg text-sm shadow-lg animate-fade-in">
          {error}
        </div>
      )}

      {state.labelingBreak && (
        <LabelingBreakBanner endTime={state.labelingBreak.endTime} />
      )}

      {seerResults.length > 0 && state.phase !== 'lobby' && state.phase !== 'game_over' && (
        <div className="fixed top-4 right-4 z-50 flex flex-col gap-2 max-w-xs w-full pointer-events-none">
          {seerResults.slice(-3).map((r) => (
            <SeerResultCard
              key={r.id}
              result={r}
              onDismiss={() => setSeerResults(prev => prev.filter(item => item.id !== r.id))}
            />
          ))}
        </div>
      )}

      <main className="flex-1 flex flex-col">
        {state.phase === 'lobby' && socket && (
          <Lobby state={state} socket={socket} onStart={handleStart} starting={starting} onReady={handleReady} />
        )}
        {state.phase === 'role_reveal' && (
          <RoleReveal state={state} onAcknowledge={handleAcknowledge} acknowledged={acknowledged} />
        )}
        {state.phase === 'night' && socket && (
          <NightPhase state={state} socket={socket} messages={messages} />
        )}
        {state.phase === 'mayor_advocacy' && socket && (
          <MayorAdvocacy state={state} socket={socket} messages={messages} />
        )}
        {state.phase === 'mayor_election' && socket && (
          <MayorElection state={state} socket={socket} messages={messages} />
        )}
        {(state.phase === 'day_discussion' || state.phase === 'day_vote') && socket && (
          <DayPhase state={state} socket={socket} messages={messages} />
        )}
        {state.phase === 'day_result' && socket && (
          <DayResult state={state} socket={socket} />
        )}
        {state.phase === 'game_over' && (
          <GameOver state={state} onPlayAgain={handlePlayAgain} />
        )}
      </main>

      {socket && ['night', 'mayor_advocacy', 'mayor_election', 'day_discussion', 'day_vote'].includes(state.phase) && (
        <NotePanel
          socket={socket}
          phaseLabel={state.phase === 'night' ? `Night ${state.round}` : `Day ${state.round} — ${state.phase.replace('_', ' ')}`}
        />
      )}

      {socket && LABELABLE_PHASES.has(state.phase) && (
        <LabelPanel
          socket={socket}
          state={state}
          messages={messages}
          autoOpenTrigger={labelAutoOpenTrigger}
        />
      )}
    </div>
  )
}

function SeerResultCard({
  result,
  onDismiss
}: {
  result: SeerResult & { id: string; endTime: number }
  onDismiss: () => void
}) {
  const [timeLeft, setTimeLeft] = useState(Math.max(0, Math.ceil((result.endTime - Date.now()) / 1000)))

  useEffect(() => {
    const interval = setInterval(() => {
      const remaining = Math.max(0, Math.ceil((result.endTime - Date.now()) / 1000))
      setTimeLeft(remaining)
    }, 250)
    return () => clearInterval(interval)
  }, [result.endTime])

  return (
    <div
      className={`pointer-events-auto flex items-center justify-between gap-3 px-4 py-3 rounded-xl border text-sm shadow-lg backdrop-blur-md transition-all duration-300 animate-fade-in ${
        result.isWerewolf
          ? 'bg-red-950/80 border-red-700/60 text-red-200'
          : 'bg-indigo-950/80 border-indigo-700/60 text-indigo-200'
      }`}
    >
      <div className="flex items-start gap-2">
        <span className="text-base select-none">🔮</span>
        <div className="leading-snug flex-1">
          <div className="flex items-center gap-2">
            <p className="font-semibold text-[10px] opacity-70 uppercase tracking-wider text-slate-400">Investigation Result</p>
            <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-slate-800/80 text-slate-400 font-mono font-bold select-none leading-none">
              {timeLeft}s
            </span>
          </div>
          <p className="mt-0.5 text-slate-200">
            <span className="font-bold text-slate-100">{result.targetName}</span>
            {result.isWerewolf ? ' is a werewolf!' : ' is a human.'}
          </p>
        </div>
      </div>
      <button
        type="button"
        onClick={onDismiss}
        className="text-lg leading-none p-1 -mr-1 opacity-50 hover:opacity-100 transition-opacity cursor-pointer select-none text-slate-400"
        title="Dismiss result"
      >
        &times;
      </button>
    </div>
  )
}
