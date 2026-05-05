export type Role = 'werewolf' | 'villager' | 'seer' | 'doctor' | 'mayor'
export type Phase = 'lobby' | 'role_reveal' | 'night' | 'day_discussion' | 'day_vote' | 'game_over'
export type Winner = 'villagers' | 'werewolves' | null

export interface Player {
  id: string
  name: string
  role: Role | null
  isAlive: boolean
  socketId: string
  isHost: boolean
  roleAcknowledged: boolean
}

export interface NightActions {
  werewolfVotes: Record<string, string>
  seerTarget: string | null
  doctorTarget: string | null
  completed: {
    werewolves: boolean
    seer: boolean
    doctor: boolean
  }
}

export interface DayVotes {
  votes: Record<string, string>
}

export interface GameState {
  id: string
  roomCode: string
  phase: Phase
  round: number
  players: Player[]
  nightActions: NightActions
  dayVotes: DayVotes
  lastEliminated: { playerId: string; playerName: string; role: Role } | null
  winner: Winner
  hostId: string
  mayorId: string | null
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
  aliveWerewolvesVoted?: string[]
  mayorId: string | null
  phaseEndTime: number | null
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
  'game:start': (cb: (r: { success: boolean; error?: string }) => void) => void
  'game:acknowledge_role': () => void
  'chat:send': (content: string) => void
  'night:werewolf_vote': (targetId: string) => void
  'night:seer_investigate': (targetId: string) => void
  'night:doctor_save': (targetId: string) => void
  'day:vote': (targetId: string) => void
  'phase:advance': () => void
}
