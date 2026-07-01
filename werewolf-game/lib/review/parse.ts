import type {
  ParsedGame,
  ParsedLabels,
  RosterEntry,
  TimelineEvent,
  EventKind,
} from './types'

// ── CSV parsing ──────────────────────────────────────────────────────────────

// Minimal RFC-4180-ish CSV parser: handles quoted fields, escaped quotes (""),
// and commas/newlines embedded inside quoted fields. The export quotes every
// field, but we don't rely on that. Returns a list of string rows.
export function parseCsv(text: string): string[][] {
  const rows: string[][] = []
  let field = ''
  let row: string[] = []
  let inQuotes = false
  let i = 0
  // Normalize Windows line endings so a stray \r never sneaks into a field.
  const s = text.replace(/\r\n/g, '\n').replace(/\r/g, '\n')

  const endField = () => {
    row.push(field)
    field = ''
  }
  const endRow = () => {
    endField()
    rows.push(row)
    row = []
  }

  while (i < s.length) {
    const c = s[i]
    if (inQuotes) {
      if (c === '"') {
        if (s[i + 1] === '"') {
          field += '"'
          i += 2
          continue
        }
        inQuotes = false
        i++
        continue
      }
      field += c
      i++
      continue
    }
    if (c === '"') {
      inQuotes = true
      i++
      continue
    }
    if (c === ',') {
      endField()
      i++
      continue
    }
    if (c === '\n') {
      endRow()
      i++
      continue
    }
    field += c
    i++
  }
  // Flush the trailing field/row if the file didn't end with a newline.
  if (field.length > 0 || row.length > 0) endRow()
  return rows
}

const KNOWN_KINDS = new Set<EventKind>(['chat', 'system', 'night_action', 'day_vote', 'note'])

function toTimestamp(value: string): number {
  const t = Date.parse(value)
  return Number.isNaN(t) ? 0 : t
}

function toRound(value: string): number {
  const n = parseInt(value, 10)
  return Number.isNaN(n) ? 0 : n
}

// Parse the exported game CSV into a normalized, timestamp-sorted game record.
// The export groups rows by type (chat, then night_action, etc.), so we always
// re-sort by timestamp to reconstruct true chronological order.
export function parseGameCsv(text: string): ParsedGame {
  const rows = parseCsv(text)
  if (rows.length === 0) {
    throw new Error('CSV is empty.')
  }

  const header = rows[0].map(h => h.trim())
  const idx = (name: string) => header.indexOf(name)
  const iType = idx('type')
  const iContent = idx('content')
  if (iType === -1 || iContent === -1) {
    throw new Error('CSV header is missing expected columns (type, content, …). Is this a game export?')
  }

  const col = {
    type: iType,
    gameId: idx('game_id'),
    roomCode: idx('room_code'),
    gameMode: idx('game_mode'),
    winner: idx('winner'),
    round: idx('round'),
    phase: idx('phase'),
    playerName: idx('player_name'),
    playerRole: idx('player_role'),
    targetName: idx('target_name'),
    content: iContent,
    isSystem: idx('is_system'),
    timestamp: idx('timestamp'),
  }

  const at = (row: string[], i: number) => (i >= 0 && i < row.length ? row[i] : '')

  const events: TimelineEvent[] = []
  const rosterMap = new Map<string, string>()
  let gameId = ''
  let roomCode = ''
  let gameMode = ''
  let winner = ''

  for (let r = 1; r < rows.length; r++) {
    const row = rows[r]
    if (row.length === 1 && row[0] === '') continue // blank trailing line

    const rawType = at(row, col.type)
    const isSystem = at(row, col.isSystem).toLowerCase() === 'true'
    const kind: EventKind =
      rawType === 'chat' && isSystem ? 'system' : (KNOWN_KINDS.has(rawType as EventKind) ? (rawType as EventKind) : 'chat')

    const playerName = at(row, col.playerName)
    const playerRole = at(row, col.playerRole)

    if (!gameId) gameId = at(row, col.gameId)
    if (!roomCode) roomCode = at(row, col.roomCode)
    if (!gameMode) gameMode = at(row, col.gameMode)
    if (!winner) winner = at(row, col.winner)

    // Build the roster from any row that carries a non-empty role for a real
    // (non-System) player.
    if (playerRole && playerName && playerName !== 'System') {
      rosterMap.set(playerName, playerRole)
    }

    events.push({
      kind,
      round: toRound(at(row, col.round)),
      phase: at(row, col.phase),
      playerName,
      playerRole,
      targetName: at(row, col.targetName),
      content: at(row, col.content),
      isSystem,
      timestamp: toTimestamp(at(row, col.timestamp)),
    })
  }

  events.sort((a, b) => a.timestamp - b.timestamp)

  const roster: RosterEntry[] = [...rosterMap.entries()]
    .map(([name, role]) => ({ name, role }))
    .sort((a, b) => a.name.localeCompare(b.name))

  const rounds = [...new Set(events.map(e => e.round))].sort((a, b) => a - b)

  return { gameId, roomCode, gameMode, winner, roster, events, rounds }
}

// ── Labels JSON parsing ──────────────────────────────────────────────────────

export function parseLabelsJson(text: string): ParsedLabels {
  let doc: unknown
  try {
    doc = JSON.parse(text)
  } catch {
    throw new Error('Labels file is not valid JSON.')
  }
  if (!doc || typeof doc !== 'object') {
    throw new Error('Labels JSON has an unexpected shape.')
  }
  const d = doc as Record<string, unknown>
  if (!Array.isArray(d.rounds)) {
    throw new Error('Labels JSON is missing a "rounds" array. Is this the labels export?')
  }

  return {
    gameId: String(d.game_id ?? ''),
    roomCode: String(d.room_code ?? ''),
    gameMode: String(d.game_mode ?? ''),
    winner: (d.winner as string | null) ?? null,
    exportedAt: String(d.exported_at ?? ''),
    rounds: (d.rounds as ParsedLabels['rounds']),
  }
}

// ── File-type detection helper ───────────────────────────────────────────────

export function classifyFile(file: File): 'csv' | 'json' | 'unknown' {
  const name = file.name.toLowerCase()
  if (name.endsWith('.csv')) return 'csv'
  if (name.endsWith('.json')) return 'json'
  return 'unknown'
}
