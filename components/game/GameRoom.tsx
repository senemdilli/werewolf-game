'use client'

import { useEffect, useState, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import { connectSocket, disconnectSocket } from '@/lib/socket-client'
import type { ClientGameState, ChatMessage, SeerResult } from '@/types/game'
import type { GameSocket } from '@/app/room/[code]/page'
import Lobby from './Lobby'
import RoleReveal from './RoleReveal'
import NightPhase from './NightPhase'
import MayorElection from './MayorElection'
import DayPhase from './DayPhase'
import GameOver from './GameOver'

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
    }
  }, [roomCode, playerId])

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
      {error && (
        <div className="fixed top-4 left-1/2 -translate-x-1/2 z-50 bg-red-900 border border-red-700 text-red-100 px-4 py-2 rounded-lg text-sm shadow-lg animate-fade-in">
          {error}
        </div>
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
          <Lobby state={state} onStart={handleStart} starting={starting} />
        )}
        {state.phase === 'role_reveal' && (
          <RoleReveal state={state} onAcknowledge={handleAcknowledge} acknowledged={acknowledged} />
        )}
        {state.phase === 'night' && socket && (
          <NightPhase state={state} socket={socket} messages={messages} />
        )}
        {state.phase === 'mayor_election' && socket && (
          <MayorElection state={state} socket={socket} />
        )}
        {(state.phase === 'day_discussion' || state.phase === 'day_vote') && socket && (
          <DayPhase state={state} socket={socket} messages={messages} />
        )}
        {state.phase === 'game_over' && (
          <GameOver state={state} onPlayAgain={handlePlayAgain} />
        )}
      </main>
    </div>
  )
}
