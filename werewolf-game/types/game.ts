export type Role = 'werewolf' | 'villager' | 'seer' | 'witch'
export type Phase =
  | 'lobby'
  | 'role_reveal'
  | 'night'
  | 'mayor_advocacy'
  | 'mayor_election'
  | 'day_discussion'
  | 'day_vote'
  | 'day_result'
  | 'game_over'

export type GameMode = 'classic' | 'arena'
export const DEFAULT_GAME_MODE: GameMode = 'classic'

export type WitchSelfHealSetting = 'always' | 'first_round' | 'never'

export type DayVoteOutcome = 'eliminated' | 'tie' | 'skipped'

export const SKIP_VOTE = 'skip' as const
export const WOLF_VOTE_NOBODY = 'nobody' as const
export type Winner = 'villagers' | 'werewolves' | null

export type TrustDimension = 'alignment' | 'information' | 'consistency'
export type Confidence = 'low' | 'medium' | 'high'

export type LabelCheckpoint = 'before_discussion' | 'before_voting' | 'after_voting'

export interface LabelTrustUpdateInput {
  dimension: TrustDimension
  score: number  // 1..7
  confidence: Confidence
}

export interface LabelTargetInput {
  playerId: string
  reasoning: string
  updates: LabelTrustUpdateInput[]
}

export interface LabelSubmitInput {
  targets: LabelTargetInput[]
}

export interface Player {
  id: string
  name: string
  originalName?: string
  role: Role | null
  isAlive: boolean
  socketId: string
  isHost: boolean
  roleAcknowledged: boolean
  isReady: boolean
  isBot?: boolean
  isSpectator?: boolean
}

export interface WolfArenaRound {
  round: number
  votes: Record<string, string>  // wolfId -> targetId | WOLF_VOTE_NOBODY
}

export interface WolfArenaState {
  order: string[]                // wolf IDs in turn order for this night
  round: number                  // 1..3
  turn: number                   // index into order
  currentVotes: Record<string, string>
  history: WolfArenaRound[]
  resolved: boolean
}

export interface NightActions {
  werewolfVotes: Record<string, string>
  killTarget: string | null      // resolved when all wolves voted — shown to witch
  seerTarget: string | null
  witchHeal: string | null
  witchKill: string | null
  wolfArena: WolfArenaState | null  // only used when gameMode === 'arena' and >1 wolves
  completed: {
    werewolves: boolean
    seer: boolean
    witch: boolean
  }
}

export interface DayVotes {
  votes: Record<string, string>
}

export interface WitchPotions {
  heal: boolean
  kill: boolean
}

export type ConversationContext = 'mayor' | 'day'

export interface ConversationHistoryEntry {
  round: number
  speakerId: string
  speakerName: string
}

export interface ConversationState {
  active: boolean
  context: ConversationContext
  round: number
  maxRounds: number
  sub: 'bid' | 'speak'
  bids: Record<string, number>   // playerId → 1..5 (cleared between rounds; private)
  bidEndTime: number | null
  speakerId: string | null
  speakerName: string | null
  speakerEndTime: number | null
  // FIFO of player IDs who were @-mentioned by a speaker and earn the next speak
  // slots without bidding. Each pop still consumes one round (counts toward maxRounds).
  pendingSpeakers: string[]
  history: ConversationHistoryEntry[]
}

export interface AdvocacyState {
  active: boolean
  order: string[]
  turn: number
  endTime: number | null
}

export interface MayorRunoffState {
  active: boolean
  candidates: string[]
  votes: Record<string, string>  // voterId → candidateId
  endTime: number | null
}

export interface GameState {
  id: string
  roomCode: string
  gameMode: GameMode
  witchSelfHeal: WitchSelfHealSetting
  speakDuration: number
  bidDuration: number
  phase: Phase
  round: number
  players: Player[]
  nightActions: NightActions
  dayVotes: DayVotes
  mayorVotes: Record<string, string>   // voterID → targetID during mayor_election
  mayorId: string | null
  mayorElected: boolean                // true after first election
  postElectionPhase: 'day_discussion' | 'night' | null
  witchPotions: WitchPotions
  lastEliminated: { playerId: string; playerName: string; role: Role } | null
  dayVoteOutcome: DayVoteOutcome | null
  winner: Winner
  hostId: string
  phaseEndTime: number | null
  dbGameId: string | null
  // Arena-only sub-states (null in classic mode)
  conversation: ConversationState | null
  advocacy: AdvocacyState | null
  mayorRunoff: MayorRunoffState | null
  // Arena day vote: when set, mayor will break a tie from a closed vote
  pendingMayorTiebreak: string[] | null
  // Active trust-labeling checkpoint (null when no checkpoint is open).
  // While set, the active phase timer is paused and the UI shows a modal.
  labelCheckpoint: LabelCheckpoint | null
  // Per-player decision flag for the current checkpoint. Submitting or skipping
  // both set this to true. The checkpoint resolves once every alive player has
  // a true entry here.
  labelDecisions: Record<string, boolean>
  // Testing/sandbox mode: when true, bot players auto-act on every saveGame.
  isSandbox?: boolean
  forceRandomNames?: boolean
  useColorsAsNames?: boolean
}

export interface PublicPlayer {
  id: string
  name: string
  isAlive: boolean
  isHost: boolean
  role?: Role
  hasVoted?: boolean
  isMayor?: boolean
  isReady?: boolean
  isBot?: boolean
  isSpectator?: boolean
}

export interface WolfArenaView {
  order: string[]
  round: number
  turn: number
  currentVotes: Record<string, string>
  history: WolfArenaRound[]
  myTurn: boolean
  resolved: boolean
}

export interface ConversationView {
  active: boolean
  context: ConversationContext
  round: number
  maxRounds: number
  sub: 'bid' | 'speak'
  myBid: number | null
  bidEndTime: number | null
  speakerId: string | null
  speakerName: string | null
  speakerEndTime: number | null
  bidsSubmittedCount: number
  pendingSpeakers: string[]
  history: ConversationHistoryEntry[]
}

export interface AdvocacyView {
  active: boolean
  order: string[]
  turn: number
  endTime: number | null
  currentSpeakerId: string | null
  myTurn: boolean
}

export interface MayorRunoffView {
  active: boolean
  candidates: string[]
  myVote: string | null
  endTime: number | null
  votesSubmitted: number
}

export interface ClientGameState {
  id: string
  roomCode: string
  gameMode: GameMode
  witchSelfHeal: WitchSelfHealSetting
  speakDuration: number
  bidDuration: number
  phase: Phase
  round: number
  players: PublicPlayer[]
  myRole: Role | null
  myId: string
  winner: Winner
  lastEliminated: { playerId: string; playerName: string; role: Role } | null
  dayVoteOutcome: DayVoteOutcome | null
  werewolfTeammates?: string[]
  nightActionsCompleted: boolean
  dayVotes: Record<string, string>
  mayorVotes: Record<string, string>
  mayorId: string | null
  aliveWerewolvesVoted?: string[]
  phaseEndTime: number | null
  // werewolf-only (arena mode, >1 wolves)
  wolfArena?: WolfArenaView | null
  // witch-only fields
  wolvesActed?: boolean
  nightKillTarget?: { id: string; name: string } | null
  witchPotions?: WitchPotions
  // Arena conversation/advocacy/runoff (null when inactive)
  conversation?: ConversationView | null
  advocacy?: AdvocacyView | null
  mayorRunoff?: MayorRunoffView | null
  // Arena day-vote tiebreak: set on the mayor's client only
  mayorTiebreakCandidates?: string[] | null
  // Public flag — true while the mayor is deciding a tied day-vote
  mayorTiebreakPending?: boolean
  // Active labeling checkpoint (null when no checkpoint open).
  labelCheckpoint: LabelCheckpoint | null
  // Whether the current player has already decided (submitted or skipped) in this checkpoint.
  labelMeDecided: boolean
  // Counts for the "X of N ready" progress chip.
  labelDecidedCount: number
  labelDecidedTotal: number
  isSandbox?: boolean
  serverTime: number
  forceRandomNames?: boolean
  useColorsAsNames?: boolean
}

export interface ChatMessage {
  id: string
  playerId: string | null
  playerName: string
  role: Role | null
  content: string
  phase: Phase
  round: number
  isSystem: boolean
  timestamp: number
}

export interface SeerResult {
  targetName: string
  isWerewolf: boolean
}

export interface ServerToClientEvents {
  'game:state': (state: ClientGameState) => void
  'chat:message': (msg: ChatMessage) => void
  'chat:history': (history: ChatMessage[]) => void
  'seer:result': (result: SeerResult) => void
  'room:kicked': (reason: string) => void
  'room:session_replaced': () => void
  error: (message: string) => void
}

export interface ClientToServerEvents {
  'room:create': (data: { playerName: string; gameMode: GameMode; witchSelfHeal?: WitchSelfHealSetting; speakDuration?: number; bidDuration?: number; isSandbox?: boolean; sandboxBotCount?: number; forceRandomNames?: boolean; useColorsAsNames?: boolean }, cb: (r: { roomCode: string; playerId: string }) => void) => void
  'room:join': (data: { roomCode: string; playerName: string }, cb: (r: { success: boolean; playerId?: string; error?: string }) => void) => void
  'room:rejoin': (data: { roomCode: string; playerId: string }, cb: (r: { success: boolean; error?: string }) => void) => void
  'room:ready': () => void
  'room:toggle_spectator': () => void
  'room:kick': (targetPlayerId: string) => void
  'note:save': (content: string) => void
  'game:start': (cb: (r: { success: boolean; error?: string }) => void) => void
  'game:acknowledge_role': () => void
  'chat:send': (content: string) => void
  'night:werewolf_vote': (targetId: string) => void
  'night:seer_investigate': (targetId: string) => void
  'night:witch_action': (data: { heal: string | null; kill: string | null }) => void
  'day:vote': (targetId: string) => void
  'mayor:vote': (targetId: string) => void
  'mayor:runoff_vote': (candidateId: string) => void
  'mayor:tiebreak_decision': (targetId: string | null) => void
  'conversation:bid': (bid: number) => void
  'phase:advance': () => void
  'label:submit': (data: LabelSubmitInput, cb: (r: { success: boolean; error?: string }) => void) => void
  'label:skip': (cb: (r: { success: boolean; error?: string }) => void) => void
  'label:force_skip': (cb: (r: { success: boolean; error?: string }) => void) => void
  'game:force_start_night': (cb: (r: { success: boolean; error?: string }) => void) => void
}
