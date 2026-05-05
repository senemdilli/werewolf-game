'use client'

import type { PublicPlayer, Role } from '@/types/game'

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
  onSelect?: (playerId: string) => void
  selectedId?: string
  selectable?: boolean
  excludeId?: string
}

export default function PlayerList({
  players,
  myId,
  showVotes,
  onSelect,
  selectedId,
  selectable,
  excludeId,
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
              <span className="text-sm font-medium truncate">
                {p.name}
                {isMe && <span className="ml-1 text-xs text-slate-400">(you)</span>}
                {p.isHost && <span className="ml-1 text-xs text-violet-400">host</span>}
              </span>
            </div>
            <div className="flex items-center gap-2 shrink-0">
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
            </div>
          </li>
        )
      })}
    </ul>
  )
}
