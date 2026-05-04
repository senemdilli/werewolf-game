import type { Server, Socket } from 'socket.io'
import type { ServerToClientEvents, ClientToServerEvents } from '@/types/game'
import { createInitialState, getGame, saveGame } from '@/server/game/state'
import { buildClientState } from '@/server/game/state'
import { v4 as uuidv4 } from 'uuid'

type GameSocket = Socket<ClientToServerEvents, ServerToClientEvents>
type GameServer = Server<ClientToServerEvents, ServerToClientEvents>

function generateRoomCode(): string {
  return Math.random().toString(36).substring(2, 8).toUpperCase()
}

export function registerRoomHandlers(io: GameServer, socket: GameSocket) {
  socket.on('room:create', async (playerName, cb) => {
    try {
      let roomCode = generateRoomCode()
      let existing = await getGame(roomCode)
      while (existing) {
        roomCode = generateRoomCode()
        existing = await getGame(roomCode)
      }

      const state = createInitialState(roomCode, socket.id, playerName)
      const hostId = state.players[0].id

      await saveGame(state)

      socket.data.playerId = hostId
      socket.data.roomCode = roomCode
      socket.join(`room:${roomCode}`)

      cb({ roomCode, playerId: hostId })
    } catch (err) {
      console.error('[room:create]', err)
      socket.emit('error', 'Failed to create room')
    }
  })

  socket.on('room:join', async ({ roomCode, playerName }, cb) => {
    try {
      const state = await getGame(roomCode)
      if (!state) return cb({ success: false, error: 'Room not found' })
      if (state.phase !== 'lobby') return cb({ success: false, error: 'Game already in progress' })
      if (state.players.length >= 12) return cb({ success: false, error: 'Room is full' })

      const playerId = uuidv4()
      state.players.push({
        id: playerId,
        name: playerName,
        role: null,
        isAlive: true,
        socketId: socket.id,
        isHost: false,
        roleAcknowledged: false,
      })

      await saveGame(state)

      socket.data.playerId = playerId
      socket.data.roomCode = roomCode
      socket.join(`room:${roomCode}`)

      for (const player of state.players) {
        const clientState = buildClientState(state, player.id)
        io.to(player.socketId).emit('game:state', clientState)
      }

      cb({ success: true, playerId })
    } catch (err) {
      console.error('[room:join]', err)
      cb({ success: false, error: 'Failed to join room' })
    }
  })

  socket.on('room:rejoin', async ({ roomCode, playerId }, cb) => {
    try {
      const state = await getGame(roomCode)
      if (!state) return cb({ success: false, error: 'Room not found' })

      const player = state.players.find(p => p.id === playerId)
      if (!player) return cb({ success: false, error: 'Player not found in room' })

      player.socketId = socket.id
      await saveGame(state)

      socket.data.playerId = playerId
      socket.data.roomCode = roomCode
      socket.join(`room:${roomCode}`)

      if (player.role === 'werewolf') {
        socket.join(`wolves:${roomCode}`)
      }

      const clientState = buildClientState(state, playerId)
      socket.emit('game:state', clientState)

      cb({ success: true })
    } catch (err) {
      console.error('[room:rejoin]', err)
      cb({ success: false, error: 'Failed to rejoin room' })
    }
  })

  socket.on('disconnect', async () => {
    const { playerId, roomCode } = socket.data
    if (!playerId || !roomCode) return

    try {
      const state = await getGame(roomCode)
      if (!state) return

      if (state.phase === 'lobby') {
        state.players = state.players.filter(p => p.id !== playerId)
        if (state.players.length === 0) {
          return
        }
        if (state.hostId === playerId && state.players.length > 0) {
          state.players[0].isHost = true
          state.hostId = state.players[0].id
        }
        await saveGame(state)

        for (const p of state.players) {
          const cs = buildClientState(state, p.id)
          io.to(p.socketId).emit('game:state', cs)
        }
      }
    } catch (err) {
      console.error('[disconnect]', err)
    }
  })
}
