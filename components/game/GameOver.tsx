'use client'

import type { ClientGameState } from '@/types/game'
import PlayerList from './PlayerList'

interface Props {
  state: ClientGameState
  onPlayAgain: () => void
}

export default function GameOver({ state, onPlayAgain }: Props) {
  const won = state.winner === 'villagers' ? 'Villagers' : 'Werewolves'
  const myRole = state.myRole
  const iWon =
    (state.winner === 'villagers' && myRole !== 'werewolf') ||
    (state.winner === 'werewolves' && myRole === 'werewolf')

  return (
    <div className="flex flex-col items-center justify-center min-h-screen px-4 py-8">
      <div className="w-full max-w-md text-center animate-fade-in">
        <div className="text-6xl mb-4">{state.winner === 'villagers' ? '🏘' : '🐺'}</div>
        <h1 className="text-4xl font-black mb-2">
          {won} Win!
        </h1>
        <p className={`text-lg font-semibold mb-8 ${iWon ? 'text-emerald-400' : 'text-red-400'}`}>
          {iWon ? 'You won! 🎉' : 'You lost.'}
        </p>

        <div className="bg-slate-900 border border-slate-700 rounded-xl p-4 mb-6 text-left">
          <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wide mb-3">
            Final roles — {state.round} rounds played
          </h2>
          <PlayerList players={state.players} myId={state.myId} />
        </div>

        <button
          onClick={onPlayAgain}
          className="px-6 py-3 bg-violet-600 hover:bg-violet-700 text-white font-semibold rounded-lg transition-colors"
        >
          Back to Home
        </button>
      </div>
    </div>
  )
}
