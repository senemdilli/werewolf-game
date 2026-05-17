import type { Server, Socket } from 'socket.io'
import type { ServerToClientEvents, ClientToServerEvents, ChatMessage, Phase } from '@/types/game'
import { getGame } from '@/server/game/state'
import { prisma } from '@/lib/prisma'
import { v4 as uuidv4 } from 'uuid'

type GameSocket = Socket<ClientToServerEvents, ServerToClientEvents>
type GameServer = Server<ClientToServerEvents, ServerToClientEvents>

export function registerChatHandlers(io: GameServer, socket: GameSocket) {
  socket.on('chat:send', async (content) => {
    try {
      const { playerId, roomCode } = socket.data
      if (!playerId || !roomCode) return

      const trimmed = content.trim().slice(0, 500)
      if (!trimmed) return

      const state = await getGame(roomCode)
      if (!state) return

      const player = state.players.find(p => p.id === playerId)
      if (!player) return

      const isNight = state.phase === 'night'

      if (isNight) {
        if (player.role !== 'werewolf' || !player.isAlive) return
      } else {
        if (!['day_discussion', 'day_vote', 'mayor_election', 'lobby'].includes(state.phase)) return
        if (state.phase !== 'lobby' && !player.isAlive) return
      }

      const msg: ChatMessage = {
        id: uuidv4(),
        playerId,
        playerName: player.name,
        role: null,
        content: trimmed,
        phase: state.phase as Phase,
        round: state.round,
        isSystem: false,
        timestamp: Date.now(),
      }

      if (isNight) {
        io.to(`wolves:${roomCode}`).emit('chat:message', msg)
      } else {
        io.to(`room:${roomCode}`).emit('chat:message', msg)
      }

      if (state.dbGameId && state.phase !== 'lobby') {
        const dbPhase = isNight ? 'NIGHT' : 'DAY'
        await prisma.message.create({
          data: {
            gameId: state.dbGameId,
            playerId: await getDbPlayerId(state.dbGameId, player.name),
            playerName: player.name,
            role: player.role?.toUpperCase() as 'WEREWOLF' | 'VILLAGER' | 'SEER' | 'WITCH',
            content: trimmed,
            phase: dbPhase,
            round: state.round,
          },
        }).catch(err => console.error('[chat persist]', err))
      }
    } catch (err) {
      console.error('[chat:send]', err)
    }
  })
}

async function getDbPlayerId(gameId: string, name: string): Promise<string | undefined> {
  const player = await prisma.player.findFirst({ where: { gameId, name } })
  return player?.id
}
