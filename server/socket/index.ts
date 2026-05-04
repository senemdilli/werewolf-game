import type { Server } from 'socket.io'
import type { ServerToClientEvents, ClientToServerEvents } from '@/types/game'
import { registerRoomHandlers } from './handlers/room'
import { registerGameHandlers } from './handlers/game'
import { registerChatHandlers } from './handlers/chat'

type GameServer = Server<ClientToServerEvents, ServerToClientEvents>

export function setupSocketHandlers(io: GameServer) {
  io.on('connection', (socket) => {
    socket.data = {}

    registerRoomHandlers(io, socket)
    registerGameHandlers(io, socket)
    registerChatHandlers(io, socket)
  })
}
