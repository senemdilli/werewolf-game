import { prisma } from '@/lib/prisma'

export async function GET(_req: Request, { params }: { params: Promise<{ gameId: string }> }) {
  const { gameId } = await params

  const [game, labels] = await Promise.all([
    prisma.game.findUnique({ where: { id: gameId } }),
    prisma.label.findMany({
      where: { gameId },
      include: {
        observer: true,
        event: true,
        trustUpdates: { include: { target: true } },
      },
      orderBy: { createdAt: 'asc' },
    }),
  ])

  if (!game) return Response.json({ error: 'Game not found' }, { status: 404 })

  const payload = {
    game_id: game.id,
    room_code: game.roomCode,
    game_mode: game.gameMode,
    winner: game.winner,
    exported_at: new Date().toISOString(),
    labels: labels.map(l => {
      // Group updates by target so each target appears once with all its dimensions.
      const byTarget = new Map<string, {
        target: { id: string; name: string; role: string }
        alignment?: { score: number; confidence: string }
        information?: { score: number; confidence: string }
        consistency?: { score: number; confidence: string }
      }>()
      for (const u of l.trustUpdates) {
        let row = byTarget.get(u.targetId)
        if (!row) {
          row = {
            target: { id: u.target.id, name: u.target.name, role: u.target.role },
          }
          byTarget.set(u.targetId, row)
        }
        const dimKey = u.dimension.toLowerCase() as 'alignment' | 'information' | 'consistency'
        row[dimKey] = { score: u.score, confidence: u.confidence }
      }

      return {
        id: l.id,
        created_at: l.createdAt.toISOString(),
        phase: l.phase,
        round: l.round,
        observer: { id: l.observer.id, name: l.observer.name, role: l.observer.role },
        event: l.event
          ? {
              id: l.event.id,
              is_system: l.event.isSystem,
              content: l.event.content,
              phase: l.event.phase,
              round: l.event.round,
            }
          : null,
        action: l.action,
        action_args: l.actionArgs,
        reasoning: l.reasoning,
        trust_updates: [...byTarget.values()],
      }
    }),
  }

  return new Response(JSON.stringify(payload, null, 2), {
    headers: {
      'Content-Type': 'application/json',
      'Content-Disposition': `attachment; filename="game-${game.roomCode}-${game.id.slice(0, 8)}-labels.json"`,
    },
  })
}
