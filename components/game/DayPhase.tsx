'use client'

import { useState } from 'react'
import type { ClientGameState, ChatMessage } from '@/types/game'
import type { GameSocket } from '@/app/room/[code]/page'
import Button from '@/components/ui/Button'
import PlayerList from './PlayerList'
import Chat from './Chat'

interface Props {
  state: ClientGameState
  socket: GameSocket
  messages: ChatMessage[]
}

export default function DayPhase({ state, socket, messages }: Props) {
  const [selected, setSelected] = useState<string | null>(null)
  const [voted, setVoted] = useState(false)
  const me = state.players.find(p => p.id === state.myId)
  const isAlive = me?.isAlive ?? false
  const isVoting = state.phase === 'day_vote'
  const isHost = me?.isHost
  const dayMessages = messages.filter(m => m.phase !== 'night')

  function handleVote() {
    if (!selected) return
    setVoted(true)
    socket.emit('day:vote', selected)
  }

  const hasVoted = !!state.dayVotes[state.myId]

  return (
    <div className="flex flex-col lg:flex-row gap-4 h-full p-4 max-w-5xl mx-auto w-full">
      <div className="flex-1 flex flex-col gap-4 min-w-0">
        <div className="bg-slate-900 border border-slate-700 rounded-xl p-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="text-lg">☀️</span>
              <h2 className="font-bold text-slate-100">
                Day {state.round} — {isVoting ? 'Voting' : 'Discussion'}
              </h2>
            </div>
            {isHost && !isVoting && (
              <Button size="sm" variant="warning" onClick={() => socket.emit('phase:advance')}>
                Start Vote
              </Button>
            )}
            {isHost && isVoting && (
              <Button size="sm" variant="ghost" onClick={() => socket.emit('phase:advance')}>
                Force resolve
              </Button>
            )}
          </div>
          {state.lastEliminated && (
            <div className="mt-3 p-3 bg-slate-800 rounded-lg border border-slate-700">
              <p className="text-sm text-slate-300">
                <span className="text-red-400 font-semibold">{state.lastEliminated.playerName}</span>
                {' '}was eliminated last night. They were a{' '}
                <span className="font-semibold">{state.lastEliminated.role}</span>.
              </p>
            </div>
          )}
        </div>

        <div className="bg-slate-900 border border-slate-700 rounded-xl p-4">
          <h3 className="text-sm font-semibold text-slate-400 uppercase tracking-wide mb-3">Players</h3>
          {isVoting && isAlive && !hasVoted ? (
            <>
              <p className="text-sm text-slate-300 mb-3">Select a player to vote for elimination:</p>
              <PlayerList
                players={state.players}
                myId={state.myId}
                showVotes
                onSelect={setSelected}
                selectedId={selected ?? undefined}
                selectable
                excludeId={state.myId}
              />
              <Button
                className="w-full mt-3"
                variant="danger"
                disabled={!selected || voted}
                onClick={handleVote}
              >
                Vote to eliminate {selected ? state.players.find(p => p.id === selected)?.name : '…'}
              </Button>
            </>
          ) : (
            <PlayerList
              players={state.players}
              myId={state.myId}
              showVotes={isVoting}
            />
          )}
          {isVoting && hasVoted && isAlive && (
            <p className="text-sm text-emerald-400 mt-3">✓ Your vote has been cast. Waiting for others…</p>
          )}
        </div>
      </div>

      <div className="w-full lg:w-80 bg-slate-900 border border-slate-700 rounded-xl flex flex-col" style={{ height: '480px' }}>
        <div className="p-3 border-b border-slate-700">
          <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide">Village chat</p>
        </div>
        <div className="flex-1 min-h-0">
          <Chat
            messages={dayMessages}
            onSend={content => socket.emit('chat:send', content)}
            canSend={isAlive && !isVoting}
            placeholder={isVoting ? 'Voting in progress' : 'Discuss with the village…'}
          />
        </div>
      </div>
    </div>
  )
}
