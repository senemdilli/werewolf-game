import type { Server, Socket } from 'socket.io'
import type { ServerToClientEvents, ClientToServerEvents, ChatMessage, Phase } from '@/types/game'
import { getGame } from '@/server/game/state'
import { prisma } from '@/lib/prisma'
import { v4 as uuidv4 } from 'uuid'
import { onSpeakerMessage } from './game'

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
      const isArena = state.gameMode === 'arena'

      if (isNight) {
        if (player.role !== 'werewolf' || !player.isAlive) return
        // Arena rules: no talking during the wolf night vote.
        if (isArena) return
      } else {
        if (!['day_discussion', 'day_vote', 'mayor_election', 'mayor_advocacy', 'lobby'].includes(state.phase)) return
        if (state.phase !== 'lobby' && !player.isAlive) return

        // Arena: speaking is gated by advocacy/conversation sub-state.
        if (isArena && state.phase === 'mayor_advocacy') {
          if (!state.advocacy?.active) return
          if (state.advocacy.order[state.advocacy.turn] !== playerId) return
        } else if (isArena && (state.phase === 'mayor_election' || state.phase === 'day_discussion')) {
          if (!state.conversation?.active) return
          if (state.conversation.sub !== 'speak') return
          if (state.conversation.speakerId !== playerId) return
        }
        // Arena: day_vote / mayor_election vote phase → no chat.
        if (isArena && state.phase === 'day_vote') return
        if (isArena && state.phase === 'mayor_election' && !state.conversation?.active) return
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

      // Arena: advancing advocacy / conversation after the speaker sent their one message.
      if (isArena && !isNight) {
        await onSpeakerMessage(io, roomCode, playerId, trimmed)
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
