'use client'

import type { PublicPlayer, Role } from '@/types/game'
import PlayerName from './PlayerName'

const roleColor: Record<Role, string> = {
  werewolf: 'text-red-400 bg-red-950/50 border-red-800',
  villager: 'text-blue-400 bg-blue-950/50 border-blue-800',
  seer:     'text-amber-400 bg-amber-950/50 border-amber-800',
  witch:    'text-purple-400 bg-purple-950/50 border-purple-800',
}

interface Props {
  players: PublicPlayer[]
  myId: string
  showVotes?: boolean
  showReady?: boolean
  onSelect?: (playerId: string) => void
  selectedId?: string
  selectable?: boolean
  excludeId?: string
  // When provided, renders a kick button next to every player except `myId`.
  // Only pass this when the viewer has authority to kick (e.g. lobby host).
  onKick?: (playerId: string) => void
}

export default function PlayerList({
  players,
  myId,
  showVotes,
  showReady,
  onSelect,
  selectedId,
  selectable,
  excludeId,
  onKick,
}: Props) {
  return (
    <ul className="space-y-2">
      {players.map(p => {
        const isMe = p.id === myId
        const isExcluded = p.id === excludeId
        const isSelected = p.id === selectedId
        const canSelect = selectable && p.isAlive && !isMe && !isExcluded

        return (
          <li
            key={p.id}
            onClick={() => canSelect && onSelect?.(p.id)}
            className={`
              flex items-center justify-between px-3 py-2 rounded-lg border transition-colors
              ${!p.isAlive ? 'opacity-40 line-through border-slate-800 bg-slate-900/30' : 'border-slate-700 bg-slate-800/60'}
              ${isSelected ? 'border-violet-500 bg-violet-950/50' : ''}
              ${canSelect ? 'cursor-pointer hover:border-violet-400' : ''}
            `}
          >
            <div className="flex items-center gap-2 min-w-0">
              <span className="text-sm truncate">
                <PlayerName name={p.name} role={p.role} isMe={isMe} isHost={p.isHost} />
              </span>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              {showReady && (
                <span className={`text-xs ${p.isReady ? 'text-emerald-400' : 'text-slate-600'}`}>
                  {p.isReady ? '✓ ready' : 'not ready'}
                </span>
              )}
              {showVotes && p.hasVoted && (
                <span className="text-xs text-slate-400">voted</span>
              )}
              {p.isMayor && (
                <span className="text-xs px-2 py-0.5 rounded border text-yellow-400 bg-yellow-950/50 border-yellow-700">
                  👑 mayor
                </span>
              )}
              {p.role && (
                <span className={`text-xs px-2 py-0.5 rounded border ${roleColor[p.role]}`}>
                  {p.role}
                </span>
              )}
              {!p.isAlive && (
                <span className="text-xs text-slate-500">☠</span>
              )}
              {onKick && p.id !== myId && (
                <button
                  onClick={(e) => { e.stopPropagation(); onKick(p.id) }}
                  className="text-xs px-1.5 py-0.5 rounded border border-red-900 text-red-400 hover:bg-red-950/60 cursor-pointer"
                  title={`Remove ${p.name} from the lobby`}
                  aria-label={`Remove ${p.name} from the lobby`}
                >
                  ✕
                </button>
              )}
            </div>
          </li>
        )
      })}
    </ul>
  )
}
