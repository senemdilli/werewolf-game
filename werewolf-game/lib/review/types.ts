// Types for the offline game-review dashboard. These mirror the shapes produced
// by the admin CSV export (`/api/admin/export/[gameId]`) and labels JSON export
// (`/api/admin/export/[gameId]/labels`), but are parsed entirely client-side
// from uploaded files — nothing here touches the server or Postgres.

export type EventKind = 'chat' | 'system' | 'night_action' | 'day_vote' | 'note'

// A single normalized row from the exported CSV, unified into one timeline event.
export interface TimelineEvent {
  kind: EventKind
  round: number
  // Coarse phase from the export (DAY | NIGHT). Kept as a string for resilience.
  phase: string
  playerName: string
  playerRole: string
  targetName: string
  // For chat/system: the message text. For night_action: the action type
  // (KILL/INVESTIGATE/HEAL/WITCH_KILL). For day_vote: the vote type (EXILE/MAYOR).
  content: string
  isSystem: boolean
  timestamp: number // epoch ms; 0 when unparseable
}

export interface RosterEntry {
  name: string
  role: string // WEREWOLF | VILLAGER | SEER | WITCH (uppercase, as exported)
}

export interface ParsedGame {
  gameId: string
  roomCode: string
  gameMode: string // CLASSIC | ARENA
  winner: string // VILLAGERS | WEREWOLVES | '' if unknown
  roster: RosterEntry[]
  events: TimelineEvent[] // sorted ascending by timestamp
  rounds: number[] // distinct rounds present, ascending
}

// ── Labels JSON ──────────────────────────────────────────────────────────────

export interface LabelScore {
  score: number // 1..7
  confidence: string // LOW | MEDIUM | HIGH
}

export interface LabelTarget {
  player: { id: string; name: string; role: string }
  reasoning: string
  alignment?: LabelScore
  information?: LabelScore
  consistency?: LabelScore
}

export interface LabelEntry {
  id: string
  created_at: string
  observer: { id: string; name: string; role: string }
  targets: LabelTarget[]
}

export interface LabelCheckpointGroup {
  checkpoint: string // BEFORE_DISCUSSION | BEFORE_VOTING | AFTER_VOTING
  labels: LabelEntry[]
}

export interface LabelRound {
  round: number
  checkpoints: LabelCheckpointGroup[]
}

export interface ParsedLabels {
  gameId: string
  roomCode: string
  gameMode: string
  winner: string | null
  exportedAt: string
  rounds: LabelRound[]
}

export type TrustDimension = 'alignment' | 'information' | 'consistency'
