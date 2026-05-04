'use client'

import { io, Socket } from 'socket.io-client'
import type { ServerToClientEvents, ClientToServerEvents } from '@/types/game'

type GameSocket = Socket<ServerToClientEvents, ClientToServerEvents>

let socket: GameSocket | null = null

export function getSocket(): GameSocket {
  if (!socket) {
    socket = io({
      autoConnect: false,
      transports: ['websocket', 'polling'],
    })
  }
  return socket
}

export function connectSocket(): GameSocket {
  const s = getSocket()
  if (!s.connected) s.connect()
  return s
}

export function disconnectSocket() {
  if (socket?.connected) {
    socket.disconnect()
  }
}
