import { prisma } from '@/lib/prisma'

type LabelCheckpoint = 'BEFORE_DISCUSSION' | 'BEFORE_VOTING' | 'AFTER_VOTING'

export async function GET(_req: Request, { params }: { params: Promise<{ gameId: string }> }) {
  const { gameId } = await params

  const [game, labels] = await Promise.all([
    prisma.game.findUnique({ where: { id: gameId } }),
    prisma.label.findMany({
      where: { gameId },
      include: {
        observer: true,
        targets: {
          include: {
            target: true,
            updates: true,
          },
        },
      },
      orderBy: [{ round: 'asc' }, { createdAt: 'asc' }],
    }),
  ])

  if (!game) return Response.json({ error: 'Game not found' }, { status: 404 })

  // Group labels by round → checkpoint for analysis-friendly shape.
  type LabelRow = (typeof labels)[number]
  type Grouped = Record<string, Record<string, LabelRow[]>>
  const grouped: Grouped = {}
  for (const l of labels) {
    const roundKey = String(l.round)
    const cpKey = l.checkpoint
    grouped[roundKey] ??= {}
    grouped[roundKey][cpKey] ??= []
    grouped[roundKey][cpKey].push(l)
  }

  const rounds = Object.keys(grouped)
    .map(n => parseInt(n, 10))
    .sort((a, b) => a - b)

  const ORDER: LabelCheckpoint[] = ['BEFORE_DISCUSSION', 'BEFORE_VOTING', 'AFTER_VOTING']

  const payload = {
    game_id: game.id,
    room_code: game.roomCode,
    game_mode: game.gameMode,
    winner: game.winner,
    exported_at: new Date().toISOString(),
    rounds: rounds.map(round => ({
      round,
      checkpoints: ORDER
        .filter(cp => grouped[String(round)]?.[cp])
        .map(cp => ({
          checkpoint: cp,
          labels: grouped[String(round)][cp].map(l => ({
            id: l.id,
            created_at: l.createdAt.toISOString(),
            observer: { id: l.observer.id, name: l.observer.name, role: l.observer.role },
            targets: l.targets.map(t => ({
              player: { id: t.target.id, name: t.target.name, role: t.target.role },
              reasoning: t.reasoning,
              alignment: t.updates.find(u => u.dimension === 'ALIGNMENT')
                ? {
                    score: t.updates.find(u => u.dimension === 'ALIGNMENT')!.score,
                    confidence: t.updates.find(u => u.dimension === 'ALIGNMENT')!.confidence,
                  }
                : undefined,
              information: t.updates.find(u => u.dimension === 'INFORMATION')
                ? {
                    score: t.updates.find(u => u.dimension === 'INFORMATION')!.score,
                    confidence: t.updates.find(u => u.dimension === 'INFORMATION')!.confidence,
                  }
                : undefined,
              consistency: t.updates.find(u => u.dimension === 'CONSISTENCY')
                ? {
                    score: t.updates.find(u => u.dimension === 'CONSISTENCY')!.score,
                    confidence: t.updates.find(u => u.dimension === 'CONSISTENCY')!.confidence,
                  }
                : undefined,
            })),
          })),
        })),
    })),
  }

  return new Response(JSON.stringify(payload, null, 2), {
    headers: {
      'Content-Type': 'application/json',
      'Content-Disposition': `attachment; filename="game-${game.roomCode}-${game.id.slice(0, 8)}-labels.json"`,
    },
  })
}
