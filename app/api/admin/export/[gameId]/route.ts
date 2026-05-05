import { prisma } from '@/lib/prisma'

export async function GET(_req: Request, { params }: { params: Promise<{ gameId: string }> }) {
  const { gameId } = await params

  const [game, messages, players, actions, notes] = await Promise.all([
    prisma.game.findUnique({ where: { id: gameId } }),
    prisma.message.findMany({
      where: { gameId },
      orderBy: { createdAt: 'asc' },
    }),
    prisma.player.findMany({ where: { gameId } }),
    prisma.nightAction.findMany({
      where: { gameId },
      include: { player: true, targetPlayer: true },
      orderBy: { round: 'asc' },
    }),
    prisma.playerNote.findMany({
      where: { gameId },
      include: { player: true },
      orderBy: { createdAt: 'asc' },
    }),
  ])

  if (!game) return Response.json({ error: 'Game not found' }, { status: 404 })

  const rows: string[] = [
    'type,game_id,room_code,winner,round,phase,player_name,player_role,target_name,content,is_system,timestamp',
  ]

  const playerRoleMap = new Map(players.map(p => [p.id, p.role]))

  for (const msg of messages) {
    const playerRole = (msg.playerId ? playerRoleMap.get(msg.playerId) : null) ?? msg.role ?? ''
    rows.push(csvRow([
      'message',
      game.id,
      game.roomCode,
      game.winner ?? '',
      String(msg.round),
      msg.phase,
      msg.playerName,
      playerRole,
      '',
      msg.content,
      msg.isSystem ? 'true' : 'false',
      msg.createdAt.toISOString(),
    ]))
  }

  for (const action of actions) {
    rows.push(csvRow([
      'night_action',
      game.id,
      game.roomCode,
      game.winner ?? '',
      String(action.round),
      'NIGHT',
      action.player.name,
      action.player.role,
      action.targetPlayer.name,
      action.actionType,
      'false',
      '',
    ]))
  }

  for (const note of notes) {
    rows.push(csvRow([
      'player_note',
      game.id,
      game.roomCode,
      game.winner ?? '',
      String(note.round),
      note.phase,
      note.playerName,
      playerRoleMap.get(note.playerId) ?? '',
      '',
      note.content,
      'false',
      note.createdAt.toISOString(),
    ]))
  }

  const csv = rows.join('\n')

  return new Response(csv, {
    headers: {
      'Content-Type': 'text/csv',
      'Content-Disposition': `attachment; filename="game-${game.roomCode}-${game.id.slice(0, 8)}.csv"`,
    },
  })
}

function csvRow(fields: string[]): string {
  return fields.map(f => `"${String(f).replace(/"/g, '""')}"`).join(',')
}
