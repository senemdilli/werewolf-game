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
  const [seerResults, setSeerResults] = useState<SeerResult[]>([])
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
      if (newState.phase !== 'role_reveal') setAcknowledged(false)
      if (newState.phase !== 'lobby' && newState.phase !== 'game_over') setStarting(false)
    })

    s.on('chat:message', (msg) => {
      setMessages(prev => [...prev, msg])
    })

    s.on('seer:result', (result) => {
      setSeerResults(prev => [...prev, result])
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

      {seerResults.length > 0 && state.phase === 'night' && (
        <div className="fixed top-4 right-4 z-50 space-y-2">
          {seerResults.slice(-3).map((r, i) => (
            <div
              key={i}
              className={`px-4 py-2 rounded-lg border text-sm shadow-lg ${
                r.isWerewolf
                  ? 'bg-red-950 border-red-700 text-red-200'
                  : 'bg-blue-950 border-blue-700 text-blue-200'
              }`}
            >
              🔮 {r.targetName} is{r.isWerewolf ? '' : ' not'} a werewolf
            </div>
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
