import type { Server, Socket } from 'socket.io'
import type {
  ServerToClientEvents, ClientToServerEvents,
  LabelSubmitInput, TrustDimension, Confidence, LabelCheckpoint,
} from '@/types/game'
import { getGame, saveGame } from '@/server/game/state'
import { maybeResolveCheckpoint } from './game'
import { prisma } from '@/lib/prisma'
import type { $Enums } from '@prisma/client'

type GameSocket = Socket<ClientToServerEvents, ServerToClientEvents>
type GameServer = Server<ClientToServerEvents, ServerToClientEvents>

const DIMENSIONS: TrustDimension[] = ['alignment', 'information', 'consistency']
const CONFIDENCES: Confidence[] = ['low', 'medium', 'high']

function toPrismaDimension(d: TrustDimension): $Enums.TrustDimension {
  return d.toUpperCase() as $Enums.TrustDimension
}
function toPrismaConfidence(c: Confidence): $Enums.Confidence {
  return c.toUpperCase() as $Enums.Confidence
}
function toPrismaCheckpoint(c: LabelCheckpoint): $Enums.LabelCheckpoint {
  return c.toUpperCase() as $Enums.LabelCheckpoint
}

export function registerLabelHandlers(io: GameServer, socket: GameSocket) {
  socket.on('label:submit', async (data: LabelSubmitInput, cb) => {
    const ack = typeof cb === 'function' ? cb : () => {}
    try {
      const { playerId, roomCode } = socket.data
      if (!playerId || !roomCode) return ack({ success: false, error: 'Not in a room' })

      const state = await getGame(roomCode)
      if (!state || !state.dbGameId) return ack({ success: false, error: 'Game not found' })
      if (!state.labelCheckpoint) return ack({ success: false, error: 'No labeling checkpoint open' })

      const observer = state.players.find(p => p.id === playerId)
      if (!observer || !observer.isAlive) return ack({ success: false, error: 'Only alive players can label' })
      if (state.labelDecisions[playerId]) return ack({ success: false, error: 'Already decided' })

      if (!Array.isArray(data.targets) || data.targets.length === 0) {
        return ack({ success: false, error: 'Pick at least one player to label' })
      }

      const seenTargets = new Set<string>()
      for (const t of data.targets) {
        if (!t || typeof t.playerId !== 'string') return ack({ success: false, error: 'Invalid target' })
        if (t.playerId === playerId) return ack({ success: false, error: 'Cannot label yourself' })
        if (seenTargets.has(t.playerId)) return ack({ success: false, error: 'Duplicate target' })
        seenTargets.add(t.playerId)

        const tp = state.players.find(p => p.id === t.playerId)
        if (!tp || !tp.isAlive) return ack({ success: false, error: 'Target is not an alive player' })

        const reasoning = (t.reasoning ?? '').trim()
        if (!reasoning) return ack({ success: false, error: `Reasoning is required for ${tp.name}` })
        if (reasoning.length > 2000) return ack({ success: false, error: 'Reasoning too long' })

        if (!Array.isArray(t.updates) || t.updates.length === 0) {
          return ack({ success: false, error: `Pick at least one dimension for ${tp.name}` })
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

      await prisma.label.create({
        data: {
          gameId: state.dbGameId,
          observerId: observerDb.id,
          checkpoint: toPrismaCheckpoint(state.labelCheckpoint),
          round: state.round,
          targets: {
            create: data.targets.map(t => ({
              targetId: targetDbIds.get(t.playerId)!,
              reasoning: t.reasoning.trim(),
              updates: {
                create: t.updates.map(u => ({
                  dimension: toPrismaDimension(u.dimension),
                  score: u.score,
                  confidence: toPrismaConfidence(u.confidence),
                })),
              },
            })),
          },
        },
      })

      state.labelDecisions[playerId] = true
      await saveGame(state)
      ack({ success: true })
      await maybeResolveCheckpoint(io, roomCode)
    } catch (err) {
      console.error('[label:submit]', err)
      ack({ success: false, error: 'Failed to save labels' })
    }
  })

  socket.on('label:skip', async (cb) => {
    const ack = typeof cb === 'function' ? cb : () => {}
    try {
      const { playerId, roomCode } = socket.data
      if (!playerId || !roomCode) return ack({ success: false, error: 'Not in a room' })

      const state = await getGame(roomCode)
      if (!state) return ack({ success: false, error: 'Game not found' })
      if (!state.labelCheckpoint) return ack({ success: false, error: 'No labeling checkpoint open' })

      const observer = state.players.find(p => p.id === playerId)
      if (!observer || !observer.isAlive) return ack({ success: false, error: 'Only alive players can skip' })
      if (state.labelDecisions[playerId]) return ack({ success: false, error: 'Already decided' })

      state.labelDecisions[playerId] = true
      await saveGame(state)
      ack({ success: true })
      await maybeResolveCheckpoint(io, roomCode)
    } catch (err) {
      console.error('[label:skip]', err)
      ack({ success: false, error: 'Failed to skip' })
    }
  })

  socket.on('label:force_skip', async (cb) => {
    const ack = typeof cb === 'function' ? cb : () => {}
    try {
      const { playerId, roomCode } = socket.data
      if (!playerId || !roomCode) return ack({ success: false, error: 'Not in a room' })

      const state = await getGame(roomCode)
      if (!state) return ack({ success: false, error: 'Game not found' })
      const cp = state.labelCheckpoint
      if (!cp) return ack({ success: false, error: 'No labeling checkpoint open' })

      const caller = state.players.find(p => p.id === playerId)
      if (!caller || !caller.isHost) return ack({ success: false, error: 'Only the host can force skip' })

      // Force mark all alive players as decided so maybeResolveCheckpoint resolves immediately
      const alivePlayers = state.players.filter(p => p.isAlive)
      for (const p of alivePlayers) {
        state.labelDecisions[p.id] = true
      }
      await saveGame(state)
      ack({ success: true })
      await maybeResolveCheckpoint(io, roomCode)
    } catch (err) {
      console.error('[label:force_skip]', err)
      ack({ success: false, error: 'Failed to force skip' })
    }
  })
}
