'use client'

import type { ClientGameState } from '@/types/game'
import Button from '@/components/ui/Button'
import PlayerList from './PlayerList'

interface Props {
  state: ClientGameState
  onStart: () => void
  onReady: () => void
  starting: boolean
}

export default function Lobby({ state, onStart, onReady, starting }: Props) {
  const me = state.players.find(p => p.id === state.myId)
  const isHost = me?.isHost
  const iAmReady = me?.isReady ?? false
  const canStart = state.players.length >= 4
  const readyCount = state.players.filter(p => p.isReady).length
  const allReady = canStart && readyCount === state.players.length

  return (
    <div className="flex flex-col items-center gap-8 py-8 px-4 max-w-md mx-auto w-full">
      <div className="text-center">
        <h1 className="text-3xl font-bold text-slate-100">Lobby</h1>
        <p className="text-slate-400 mt-1">
          Room code: <span className="font-mono font-bold text-violet-400 text-xl">{state.roomCode}</span>
        </p>
        <p className="text-slate-500 text-sm mt-1">Share this code with your friends</p>
      </div>

      <div className="w-full bg-slate-900 border border-slate-700 rounded-xl p-4">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-sm font-semibold text-slate-300 uppercase tracking-wide">
            Players ({state.players.length}/12)
          </h2>
          {canStart ? (
            <span className={`text-xs font-medium ${allReady ? 'text-emerald-400' : 'text-slate-400'}`}>
              {readyCount}/{state.players.length} ready
            </span>
          ) : (
            <span className="text-xs text-amber-400">Need at least 4 players</span>
          )}
        </div>
        <PlayerList players={state.players} myId={state.myId} showReady />
      </div>

      <div className="w-full bg-slate-900 border border-slate-700 rounded-xl p-4">
        <h2 className="text-sm font-semibold text-slate-300 uppercase tracking-wide mb-2">Role distribution</h2>
        <RolePreview count={state.players.length} />
      </div>

      <div className="w-full flex flex-col gap-3">
        <Button
          size="lg"
          className="w-full"
          variant={iAmReady ? 'ghost' : 'primary'}
          onClick={onReady}
        >
          {iAmReady ? 'Cancel Ready' : 'Ready'}
        </Button>

        {isHost && (
          <Button
            size="lg"
            className="w-full"
            variant="ghost"
            disabled={!canStart}
            loading={starting}
            onClick={onStart}
          >
            Force Start
          </Button>
        )}

        {allReady && (
          <p className="text-emerald-400 text-sm text-center animate-pulse">Everyone is ready — starting…</p>
        )}
      </div>
    </div>
  )
}

function RolePreview({ count }: { count: number }) {
  if (count < 4) {
    return <p className="text-slate-500 text-sm">Need at least 4 players to see role distribution</p>
  }

  const wolves = count <= 5 ? 1 : count <= 8 ? 2 : Math.floor(count / 4)
  const villagers = count - wolves - 2

  return (
    <div className="flex flex-wrap gap-2 text-xs">
      <span className="px-2 py-1 rounded bg-red-950/60 border border-red-800 text-red-400">{wolves}× Werewolf</span>
      <span className="px-2 py-1 rounded bg-amber-950/60 border border-amber-800 text-amber-400">1× Seer</span>
      <span className="px-2 py-1 rounded bg-purple-950/60 border border-purple-800 text-purple-400">1× Witch</span>
      <span className="px-2 py-1 rounded bg-blue-950/60 border border-blue-800 text-blue-400">{villagers}× Villager</span>
    </div>
  )
}
