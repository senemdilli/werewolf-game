'use client'

import { useEffect, useState } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { connectSocket } from '@/lib/socket-client'
import GameRoom from '@/components/game/GameRoom'
import type { Socket } from 'socket.io-client'
import type { ServerToClientEvents, ClientToServerEvents } from '@/types/game'

export type GameSocket = Socket<ServerToClientEvents, ClientToServerEvents>

export default function RoomPage() {
  const params = useParams()
  const router = useRouter()
  const roomCode = (params.code as string).toUpperCase()
  const [playerId, setPlayerId] = useState<string | null>(null)
  const [ready, setReady] = useState(false)

  useEffect(() => {
    const stored = sessionStorage.getItem('ww_playerId')
    if (!stored) {
      router.replace('/')
      return
    }
    setPlayerId(stored)
    connectSocket()
    setReady(true)
  }, [router])

  if (!ready || !playerId) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <p className="text-slate-400 animate-pulse">Loading…</p>
      </div>
    )
  }

  return <GameRoom roomCode={roomCode} playerId={playerId} />
}
