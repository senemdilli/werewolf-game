export type Role = 'werewolf' | 'villager' | 'seer' | 'witch'
export type Phase =
  | 'lobby'
  | 'role_reveal'
  | 'night'
  | 'mayor_election'
  | 'day_discussion'
  | 'day_vote'
  | 'game_over'
export type Winner = 'villagers' | 'werewolves' | null

export interface Player {
  id: string
  name: string
  role: Role | null
  isAlive: boolean
  socketId: string
  isHost: boolean
  roleAcknowledged: boolean
  isReady: boolean
}

export interface NightActions {
  werewolfVotes: Record<string, string>
  killTarget: string | null      // resolved when all wolves voted — shown to witch
  seerTarget: string | null
  witchHeal: string | null
  witchKill: string | null
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

export interface GameState {
  id: string
  roomCode: string
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
  winner: Winner
  hostId: string
  phaseEndTime: number | null
  dbGameId: string | null
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
}

export interface ClientGameState {
  id: string
  roomCode: string
  phase: Phase
  round: number
  players: PublicPlayer[]
  myRole: Role | null
  myId: string
  winner: Winner
  lastEliminated: { playerId: string; playerName: string; role: Role } | null
  werewolfTeammates?: string[]
  nightActionsCompleted: boolean
  dayVotes: Record<string, string>
  mayorVotes: Record<string, string>
  mayorId: string | null
  aliveWerewolvesVoted?: string[]
  phaseEndTime: number | null
  // witch-only fields
  nightKillTarget?: { id: string; name: string } | null
  witchPotions?: WitchPotions
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
  'seer:result': (result: SeerResult) => void
  error: (message: string) => void
}

export interface ClientToServerEvents {
  'room:create': (playerName: string, cb: (r: { roomCode: string; playerId: string }) => void) => void
  'room:join': (data: { roomCode: string; playerName: string }, cb: (r: { success: boolean; playerId?: string; error?: string }) => void) => void
  'room:rejoin': (data: { roomCode: string; playerId: string }, cb: (r: { success: boolean; error?: string }) => void) => void
  'room:ready': () => void
  'game:start': (cb: (r: { success: boolean; error?: string }) => void) => void
  'game:acknowledge_role': () => void
  'chat:send': (content: string) => void
  'night:werewolf_vote': (targetId: string) => void
  'night:seer_investigate': (targetId: string) => void
  'night:witch_action': (data: { heal: string | null; kill: string | null }) => void
  'day:vote': (targetId: string) => void
  'mayor:vote': (targetId: string) => void
  'phase:advance': () => void
}
