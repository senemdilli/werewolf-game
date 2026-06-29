import { prisma } from '@/lib/prisma'

export async function GET(_req: Request, { params }: { params: Promise<{ gameId: string }> }) {
  const { gameId } = await params

  const { searchParams } = new URL(_req.url)
  const format = searchParams.get('format') ?? 'csv'

  const [game, messages, players, actions, notes, dayVotes] = await Promise.all([
    prisma.game.findUnique({ where: { id: gameId } }),
    prisma.message.findMany({
      where: { gameId },
      orderBy: { createdAt: 'asc' },
    }),
    prisma.player.findMany({ where: { gameId } }),
    prisma.nightAction.findMany({
      where: { gameId },
      include: { player: true, targetPlayer: true },
      orderBy: [{ round: 'asc' }, { createdAt: 'asc' }],
    }),
    prisma.playerNote.findMany({
      where: { gameId },
      include: { player: true },
      orderBy: { createdAt: 'asc' },
    }),
    prisma.dayVote.findMany({
      where: { gameId },
      orderBy: { createdAt: 'asc' },
    }),
  ])

  if (!game) return Response.json({ error: 'Game not found' }, { status: 404 })

  const playerRoleMap = new Map(players.map((p: any) => [p.id, p.role]))

  if (format === 'json') {
    const events = [
      ...messages.map(msg => ({
        type: 'chat',
        round: msg.round,
        phase: msg.phase,
        player_name: msg.playerName,
        player_role: (msg.playerId ? playerRoleMap.get(msg.playerId) : null) ?? msg.role ?? '',
        target_name: '',
        content: msg.content,
        is_system: msg.isSystem,
        timestamp: msg.createdAt.toISOString(),
      })),
      ...actions.map(action => ({
        type: 'night_action',
        round: action.round,
        phase: 'NIGHT',
        player_name: action.player.name,
        player_role: action.player.role,
        target_name: action.targetPlayer.name,
        content: action.actionType,
        is_system: false,
        timestamp: action.createdAt.toISOString(),
      })),
      ...dayVotes.map(vote => ({
        type: 'day_vote',
        round: vote.round,
        phase: 'DAY',
        player_name: vote.playerName,
        player_role: vote.playerRole,
        target_name: vote.targetName,
        content: vote.voteType,
        is_system: false,
        timestamp: vote.createdAt.toISOString(),
      })),
      ...notes.map(note => ({
        type: 'note',
        round: note.round,
        phase: note.phase,
        player_name: note.playerName,
        player_role: playerRoleMap.get(note.playerId) ?? '',
        target_name: '',
        content: note.content,
        is_system: false,
        timestamp: note.createdAt.toISOString(),
      })),
    ]

    // Sort events chronologically by timestamp
    events.sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime())

    const payload = {
      game_id: game.id,
      room_code: game.roomCode,
      game_mode: game.gameMode,
      winner: game.winner ?? null,
      exported_at: new Date().toISOString(),
      events,
    }

    return new Response(JSON.stringify(payload, null, 2), {
      headers: {
        'Content-Type': 'application/json',
        'Content-Disposition': `attachment; filename="game-${game.roomCode}-${game.id.slice(0, 8)}.json"`,
      },
    })
  }

  // Fallback to CSV
  const rows: string[] = [
    'type,game_id,room_code,game_mode,winner,round,phase,player_name,player_role,target_name,content,is_system,timestamp',
  ]

  const csvRows: string[][] = []

  for (const msg of messages) {
    const playerRole = (msg.playerId ? playerRoleMap.get(msg.playerId) : null) ?? msg.role ?? ''
    csvRows.push([
      'chat',
      game.id,
      game.roomCode,
      game.gameMode,
      game.winner ?? '',
      String(msg.round),
      msg.phase,
      msg.playerName,
      playerRole,
      '',
      msg.content,
      msg.isSystem ? 'true' : 'false',
      msg.createdAt.toISOString(),
    ])
  }

  for (const action of actions) {
    csvRows.push([
      'night_action',
      game.id,
      game.roomCode,
      game.gameMode,
      game.winner ?? '',
      String(action.round),
      'NIGHT',
      action.player.name,
      action.player.role,
      action.targetPlayer.name,
      action.actionType,
      'false',
      action.createdAt.toISOString(),
    ])
  }

  for (const vote of dayVotes) {
    csvRows.push([
      'day_vote',
      game.id,
      game.roomCode,
      game.gameMode,
      game.winner ?? '',
      String(vote.round),
      'DAY',
      vote.playerName,
      vote.playerRole,
      vote.targetName,
      vote.voteType,
      'false',
      vote.createdAt.toISOString(),
    ])
  }

  for (const note of notes) {
    csvRows.push([
      'note',
      game.id,
      game.roomCode,
      game.gameMode,
      game.winner ?? '',
      String(note.round),
      note.phase,
      note.playerName,
      playerRoleMap.get(note.playerId) ?? '',
      '',
      note.content,
      'false',
      note.createdAt.toISOString(),
    ])
  }

  for (const r of csvRows) {
    rows.push(csvRow(r))
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
