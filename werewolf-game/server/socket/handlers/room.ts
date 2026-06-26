import type { Server, Socket } from 'socket.io'
import type { ServerToClientEvents, ClientToServerEvents } from '@/types/game'
import { createInitialState, getGame, saveGame } from '@/server/game/state'
import { buildClientState } from '@/server/game/state'
import { startGame } from './game'
import { v4 as uuidv4 } from 'uuid'
import { getChatHistory, filterChatForPlayer } from '@/server/game/chat-store'

type GameSocket = Socket<ClientToServerEvents, ServerToClientEvents>
type GameServer = Server<ClientToServerEvents, ServerToClientEvents>

function generateRoomCode(): string {
  return Math.random().toString(36).substring(2, 8).toUpperCase()
}

function uniquifyName(name: string, taken: string[]): string {
  if (!taken.includes(name)) return name
  let n = 2
  while (taken.includes(`${name}${n}`)) n++
  return `${name}${n}`
}

const pendingDisconnects = new Map<string, NodeJS.Timeout>()

export function registerRoomHandlers(io: GameServer, socket: GameSocket) {
  socket.on('room:create', async ({ playerName, gameMode, witchSelfHeal, speakDuration, bidDuration, isSandbox, sandboxBotCount, forceRandomNames, useColorsAsNames }, cb) => {
    try {
      let roomCode = generateRoomCode()
      let existing = await getGame(roomCode)
      while (existing) {
        roomCode = generateRoomCode()
        existing = await getGame(roomCode)
      }

      const safeMode = gameMode === 'arena' ? 'arena' : 'classic'
      const safeSelfHeal = ['always', 'first_round', 'never'].includes(witchSelfHeal ?? '')
        ? witchSelfHeal!
        : 'first_round'
      const safeSpeak = typeof speakDuration === 'number' && speakDuration >= 15 && speakDuration <= 100 ? speakDuration : 60
      const safeBid = typeof bidDuration === 'number' && bidDuration >= 15 && bidDuration <= 100 ? bidDuration : 30
      const state = createInitialState(roomCode, socket.id, playerName, safeMode, safeSelfHeal, safeSpeak, safeBid, !!isSandbox, !!forceRandomNames, useColorsAsNames !== false)
      const hostId = state.players[0].id

      if (isSandbox) {
        const safeBotCount = typeof sandboxBotCount === 'number' && sandboxBotCount >= 1 && sandboxBotCount <= 12
          ? sandboxBotCount
          : 3
        const botNamesPool = [
          'Lyra', 'Edmund', 'Casimir', 'Aldric', 'Beatrix',
          'Delara', 'Fiona', 'Garrett', 'Helena', 'Isidore',
          'Juliana', 'Kieran', 'Magnus', 'Nadia', 'Oswin',
          'Petra', 'Rowena', 'Stellan', 'Tamsin', 'Ulric',
          'Vesper', 'Wren', 'Xander', 'Yara', 'Zephyr'
        ]
        const botNames = botNamesPool.slice(0, safeBotCount).map(name => `Bot ${name}`)
        for (const name of botNames) {
          state.players.push({
            id: 'bot-' + uuidv4(),
            name,
            originalName: name,
            role: null,
            isAlive: true,
            socketId: 'bot-socket',
            isHost: false,
            roleAcknowledged: true,
            isReady: true,
            isBot: true,
          })
        }
      }

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

      const cleanName = playerName.trim()
      const existing = state.players.find(
        p => 
          p.name.toLowerCase() === cleanName.toLowerCase() || 
          (p.originalName && p.originalName.toLowerCase() === cleanName.toLowerCase())
      )

      if (existing) {
        // Reclaim/rejoin existing player session by matching name!
        const pending = pendingDisconnects.get(existing.id)
        if (pending) {
          clearTimeout(pending)
          pendingDisconnects.delete(existing.id)
        }

        if (existing.socketId && existing.socketId !== socket.id) {
          const oldSocket = io.sockets.sockets.get(existing.socketId)
          if (oldSocket) {
            oldSocket.emit('room:session_replaced')
            oldSocket.leave(`room:${roomCode}`)
            oldSocket.leave(`wolves:${roomCode}`)
          }
        }

        existing.socketId = socket.id
        await saveGame(state)

        socket.data.playerId = existing.id
        socket.data.roomCode = roomCode
        socket.join(`room:${roomCode}`)

        if (existing.role === 'werewolf') {
          socket.join(`wolves:${roomCode}`)
        }

        // Notify other players
        for (const player of state.players) {
          const clientState = buildClientState(state, player.id)
          io.to(player.socketId).emit('game:state', clientState)
        }

        // Sync chat history (current round only — past rounds are kept in
        // storage but hidden from the live view).
        const history = await getChatHistory(roomCode)
        const filtered = filterChatForPlayer(history, state.round, existing.role)
        socket.emit('chat:history', filtered)

        return cb({ success: true, playerId: existing.id })
      }

      if (state.phase !== 'lobby') return cb({ success: false, error: 'Game already in progress' })
      if (state.players.length >= 12) return cb({ success: false, error: 'Room is full' })

      const playerId = uuidv4()
      state.players.push({
        id: playerId,
        name: cleanName,
        originalName: cleanName,
        role: null,
        isAlive: true,
        socketId: socket.id,
        isHost: false,
        roleAcknowledged: false,
        isReady: false,
        isSpectator: false,
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
      const pending = pendingDisconnects.get(playerId)
      if (pending) {
        clearTimeout(pending)
        pendingDisconnects.delete(playerId)
      }

      const state = await getGame(roomCode)
      if (!state) return cb({ success: false, error: 'Room not found' })

      const player = state.players.find(p => p.id === playerId)
      if (!player) return cb({ success: false, error: 'Player not found in room' })

      if (player.socketId && player.socketId !== socket.id) {
        const oldSocket = io.sockets.sockets.get(player.socketId)
        if (oldSocket) {
          oldSocket.emit('room:session_replaced')
          oldSocket.leave(`room:${roomCode}`)
          oldSocket.leave(`wolves:${roomCode}`)
        }
      }

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

      const history = await getChatHistory(roomCode)
      const filtered = filterChatForPlayer(history, state.round, player.role)
      socket.emit('chat:history', filtered)

      cb({ success: true })
    } catch (err) {
      console.error('[room:rejoin]', err)
      cb({ success: false, error: 'Failed to rejoin room' })
    }
  })

  socket.on('room:ready', async () => {
    try {
      const { playerId, roomCode } = socket.data
      const state = await getGame(roomCode)
      if (!state || state.phase !== 'lobby') return

      const player = state.players.find(p => p.id === playerId)
      if (!player) return

      player.isReady = !player.isReady
      await saveGame(state)

      const activePlayers = state.players.filter(p => !p.isSpectator)
      const allReady = activePlayers.length >= 4 && activePlayers.every(p => p.isReady)
      if (allReady) {
        await startGame(io, roomCode)
      } else {
        for (const p of state.players) {
          io.to(p.socketId).emit('game:state', buildClientState(state, p.id))
        }
      }
    } catch (err) {
      console.error('[room:ready]', err)
    }
  })

  socket.on('room:toggle_spectator', async () => {
    try {
      const { playerId, roomCode } = socket.data
      const state = await getGame(roomCode)
      if (!state || state.phase !== 'lobby') return

      const player = state.players.find(p => p.id === playerId)
      if (!player) return

      player.isSpectator = !player.isSpectator
      player.isAlive = !player.isSpectator
      if (player.isSpectator) {
        player.isReady = false
      }

      await saveGame(state)

      for (const p of state.players) {
        io.to(p.socketId).emit('game:state', buildClientState(state, p.id))
      }
    } catch (err) {
      console.error('[room:toggle_spectator]', err)
    }
  })
  
  socket.on('room:kick', async (targetPlayerId) => {
    try {
      const { playerId, roomCode } = socket.data
      if (!playerId || !roomCode) return
      const state = await getGame(roomCode)
      if (!state || state.phase !== 'lobby') return

      const requester = state.players.find(p => p.id === playerId)
      if (!requester?.isHost) return
      if (targetPlayerId === playerId) return

      const target = state.players.find(p => p.id === targetPlayerId)
      if (!target) return

      // Tell the target they were kicked, then drop their socket so they can't
      // reconnect to the same player slot.
      const targetSocket = io.sockets.sockets.get(target.socketId)
      targetSocket?.emit('room:kicked', 'You were removed from the room by the host.')

      state.players = state.players.filter(p => p.id !== targetPlayerId)
      await saveGame(state)

      // Disconnect AFTER the saveGame so the disconnect handler's filter is a no-op.
      targetSocket?.disconnect(true)

      for (const p of state.players) {
        io.to(p.socketId).emit('game:state', buildClientState(state, p.id))
      }
    } catch (err) {
      console.error('[room:kick]', err)
    }
  })

  socket.on('disconnect', async () => {
    const { playerId, roomCode } = socket.data
    if (!playerId || !roomCode) return

    const timeout = setTimeout(async () => {
      pendingDisconnects.delete(playerId)
      try {
        const state = await getGame(roomCode)
        if (!state) return

        const player = state.players.find(p => p.id === playerId)
        if (!player) return
        if (player.socketId !== socket.id) return

        if (state.phase === 'lobby') {
          state.players = state.players.filter(p => p.id !== playerId)
          if (state.players.length === 0) return

          if (state.hostId === playerId && state.players.length > 0) {
            state.players[0].isHost = true
            state.hostId = state.players[0].id
          }
          await saveGame(state)

          for (const p of state.players) {
            io.to(p.socketId).emit('game:state', buildClientState(state, p.id))
          }
        } else {
          // In-game: transfer host if host left so phase:advance still works
          if (state.hostId === playerId) {
            const nextHost = state.players.find(p => p.id !== playerId && p.isAlive)
            if (nextHost) {
              state.players.forEach(p => { p.isHost = p.id === nextHost.id })
              state.hostId = nextHost.id
              await saveGame(state)
              for (const p of state.players) {
                io.to(p.socketId).emit('game:state', buildClientState(state, p.id))
              }
            }
          }
        }
      } catch (err) {
        console.error('[disconnect delayed cleanup]', err)
      }
    }, 8000)

    pendingDisconnects.set(playerId, timeout)
  })
}
