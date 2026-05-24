import type { Server, Socket } from 'socket.io'
import type {
  ServerToClientEvents, ClientToServerEvents,
  LabelCreateInput, LabelAction, TrustDimension, Confidence,
} from '@/types/game'
import { LABEL_ACTIONS } from '@/types/game'
import { getGame } from '@/server/game/state'
import { prisma } from '@/lib/prisma'
import type { $Enums } from '@prisma/client'

type GameSocket = Socket<ClientToServerEvents, ServerToClientEvents>
type GameServer = Server<ClientToServerEvents, ServerToClientEvents>

const LABELABLE_PHASES = new Set([
  'mayor_advocacy', 'mayor_election', 'day_discussion', 'day_vote', 'day_result',
])

const DIMENSIONS: TrustDimension[] = ['alignment', 'information', 'consistency']
const CONFIDENCES: Confidence[] = ['low', 'medium', 'high']

function toPrismaAction(a: LabelAction): $Enums.LabelAction {
  return a.toUpperCase() as $Enums.LabelAction
}
function toPrismaDimension(d: TrustDimension): $Enums.TrustDimension {
  return d.toUpperCase() as $Enums.TrustDimension
}
function toPrismaConfidence(c: Confidence): $Enums.Confidence {
  return c.toUpperCase() as $Enums.Confidence
}

export function registerLabelHandlers(_io: GameServer, socket: GameSocket) {
  socket.on('label:create', async (data: LabelCreateInput, cb) => {
    try {
      const ack = typeof cb === 'function' ? cb : () => {}
      const { playerId, roomCode } = socket.data
      if (!playerId || !roomCode) return ack({ success: false, error: 'Not in a room' })

      const state = await getGame(roomCode)
      if (!state || !state.dbGameId) return ack({ success: false, error: 'Game not found' })
      if (!LABELABLE_PHASES.has(state.phase)) return ack({ success: false, error: 'Labels are not enabled in this phase' })

      const observer = state.players.find(p => p.id === playerId)
      if (!observer || !observer.isAlive) return ack({ success: false, error: 'Only alive players can label' })

      // Validate action
      if (!LABEL_ACTIONS.includes(data.action)) return ack({ success: false, error: 'Invalid action' })

      // Validate reasoning
      const reasoning = (data.reasoning ?? '').trim().slice(0, 2000)
      if (!reasoning) return ack({ success: false, error: 'Reasoning is required' })

      // Validate targets
      if (!Array.isArray(data.targets) || data.targets.length === 0) {
        return ack({ success: false, error: 'At least one affected player is required' })
      }
      const seenTargets = new Set<string>()
      for (const t of data.targets) {
        if (!t || typeof t.playerId !== 'string') return ack({ success: false, error: 'Invalid target' })
        if (t.playerId === playerId) return ack({ success: false, error: 'Cannot label yourself' })
        if (seenTargets.has(t.playerId)) return ack({ success: false, error: 'Duplicate target' })
        seenTargets.add(t.playerId)
        const tp = state.players.find(p => p.id === t.playerId)
        if (!tp || !tp.isAlive) return ack({ success: false, error: 'Target is not an alive player' })
        if (!Array.isArray(t.updates) || t.updates.length === 0) {
          return ack({ success: false, error: 'Each affected player needs at least one trust update' })
        }
        const seenDims = new Set<string>()
        for (const u of t.updates) {
          if (!u || !DIMENSIONS.includes(u.dimension)) return ack({ success: false, error: 'Invalid trust dimension' })
          if (!CONFIDENCES.includes(u.confidence)) return ack({ success: false, error: 'Invalid confidence' })
          if (!Number.isInteger(u.score) || u.score < 1 || u.score > 7) {
            return ack({ success: false, error: 'Score must be an integer 1–7' })
          }
          if (seenDims.has(u.dimension)) return ack({ success: false, error: 'Duplicate dimension for the same player' })
          seenDims.add(u.dimension)
        }
      }

      // Resolve event (if provided)
      let eventDbId: string | null = null
      if (data.eventId) {
        const msg = await prisma.message.findFirst({
          where: { id: data.eventId, gameId: state.dbGameId, isSystem: true },
          select: { id: true },
        })
        if (!msg) return ack({ success: false, error: 'Unknown event' })
        eventDbId = msg.id
      }

      // Resolve DB player IDs (Player.id is per-game and matches in-game player by name).
      const observerDb = await prisma.player.findFirst({
        where: { gameId: state.dbGameId, name: observer.name },
        select: { id: true },
      })
      if (!observerDb) return ack({ success: false, error: 'Observer not found in DB' })

      const targetDbIds = new Map<string, string>()
      for (const t of data.targets) {
        const tp = state.players.find(p => p.id === t.playerId)!
        const tpDb = await prisma.player.findFirst({
          where: { gameId: state.dbGameId, name: tp.name },
          select: { id: true },
        })
        if (!tpDb) return ack({ success: false, error: 'Target not found in DB' })
        targetDbIds.set(t.playerId, tpDb.id)
      }

      const actionArgs = data.actionArgs?.toString().trim().slice(0, 500) || null

      await prisma.label.create({
        data: {
          gameId: state.dbGameId,
          observerId: observerDb.id,
          eventId: eventDbId,
          action: toPrismaAction(data.action),
          actionArgs,
          reasoning,
          phase: state.phase === 'night' ? 'NIGHT' : 'DAY',
          round: state.round,
          trustUpdates: {
            create: data.targets.flatMap(t =>
              t.updates.map(u => ({
                targetId: targetDbIds.get(t.playerId)!,
                dimension: toPrismaDimension(u.dimension),
                score: u.score,
                confidence: toPrismaConfidence(u.confidence),
              }))
            ),
          },
        },
      })

      ack({ success: true })
    } catch (err) {
      console.error('[label:create]', err)
      try { cb?.({ success: false, error: 'Failed to save label' }) } catch { /* noop */ }
    }
  })
}
