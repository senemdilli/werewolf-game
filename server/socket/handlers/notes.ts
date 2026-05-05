import type { Server, Socket } from 'socket.io'
import type { ServerToClientEvents, ClientToServerEvents } from '@/types/game'
import { getGame } from '@/server/game/state'
import { prisma } from '@/lib/prisma'

type GameSocket = Socket<ClientToServerEvents, ServerToClientEvents>
type GameServer = Server<ClientToServerEvents, ServerToClientEvents>

const ACTIVE_PHASES = new Set(['night', 'mayor_election', 'day_discussion', 'day_vote'])

export function registerNoteHandlers(_io: GameServer, socket: GameSocket) {
  socket.on('note:save', async (content) => {
    try {
      const { playerId, roomCode } = socket.data
      if (!playerId || !roomCode) return

      const trimmed = content.trim().slice(0, 2000)
      if (!trimmed) return

      const state = await getGame(roomCode)
      if (!state || !state.dbGameId) return
      if (!ACTIVE_PHASES.has(state.phase)) return

      const player = state.players.find(p => p.id === playerId)
      if (!player) return

      const dbPlayer = await prisma.player.findFirst({
        where: { gameId: state.dbGameId, name: player.name },
      })
      if (!dbPlayer) return

      await prisma.playerNote.create({
        data: {
          gameId: state.dbGameId,
          playerId: dbPlayer.id,
          playerName: player.name,
          content: trimmed,
          phase: state.phase === 'night' ? 'NIGHT' : 'DAY',
          round: state.round,
        },
      })
    } catch (err) {
      console.error('[note:save]', err)
    }
  })
}
