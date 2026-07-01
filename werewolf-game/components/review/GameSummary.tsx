'use client'

import type { ParsedGame } from '@/lib/review/types'
import { roleBadgeClass, roleLabel } from './roleStyle'

interface Props {
  game: ParsedGame
  hasLabels: boolean
}

function winnerBadge(winner: string) {
  if (!winner) return <span className="text-slate-500 text-sm">unknown</span>
  const villagers = winner.toUpperCase() === 'VILLAGERS'
  return (
    <span
      className={`text-xs px-2 py-0.5 rounded border ${
        villagers ? 'text-blue-400 bg-blue-950/50 border-blue-800' : 'text-red-400 bg-red-950/50 border-red-800'
      }`}
    >
      {winner.toLowerCase()} win
    </span>
  )
}

export default function GameSummary({ game, hasLabels }: Props) {
  return (
    <div className="rounded-xl border border-slate-700 bg-slate-900/40 p-4">
      <div className="flex flex-wrap items-center gap-3">
        <span className="font-mono font-bold text-violet-400 text-lg">{game.roomCode || '—'}</span>
        <span
          className={`text-xs px-2 py-0.5 rounded border ${
            game.gameMode.toUpperCase() === 'ARENA'
              ? 'text-amber-300 bg-amber-950/50 border-amber-800'
              : 'text-violet-300 bg-violet-950/50 border-violet-800'
          }`}
        >
          {(game.gameMode || 'classic').toLowerCase()}
        </span>
        {winnerBadge(game.winner)}
        <span className="text-xs text-slate-400">{game.roster.length} players</span>
        <span className="text-xs text-slate-400">{game.rounds.length} rounds</span>
        <span className="text-xs text-slate-400">{game.events.length} events</span>
        {hasLabels ? (
          <span className="text-xs px-2 py-0.5 rounded border text-emerald-300 bg-emerald-950/40 border-emerald-800">
            labels loaded
          </span>
        ) : (
          <span className="text-xs px-2 py-0.5 rounded border text-slate-400 border-slate-700">no labels</span>
        )}
      </div>

      <div className="mt-3 flex flex-wrap gap-2">
        {game.roster.map(p => (
          <span
            key={p.name}
            className={`text-xs px-2 py-1 rounded border ${roleBadgeClass(p.role)}`}
            title={roleLabel(p.role)}
          >
            <span className="font-semibold">{p.name}</span>
            <span className="opacity-70"> · {roleLabel(p.role)}</span>
          </span>
        ))}
      </div>

      {game.gameId && (
        <p className="mt-3 text-[10px] font-mono text-slate-600 break-all">game_id: {game.gameId}</p>
      )}
    </div>
  )
}
