'use client'

import { useState } from 'react'
import type { ClientGameState, Role } from '@/types/game'
import type { GameSocket } from '@/app/room/[code]/page'
import Button from '@/components/ui/Button'
import PlayerList from './PlayerList'
import Chat from './Chat'
import type { ChatMessage } from '@/types/game'

const rolePrompt: Record<Role, string> = {
  werewolf: 'Choose a villager to eliminate tonight.',
  seer:     'Choose a player to investigate.',
  doctor:   'Choose a player to protect tonight.',
  villager: '',
  mayor:    '',
}

interface Props {
  state: ClientGameState
  socket: GameSocket
  messages: ChatMessage[]
}

export default function NightPhase({ state, socket, messages }: Props) {
  const [selected, setSelected] = useState<string | null>(null)
  const [submitted, setSubmitted] = useState(false)
  const role = state.myRole
  const me = state.players.find(p => p.id === state.myId)
  const isAlive = me?.isAlive ?? false

  const alivePlayers = state.players.filter(p => p.isAlive)
  const isWerewolf = role === 'werewolf'
  const nightMessages = messages.filter(m => m.phase === 'night' && m.round === state.round)

  function handleAction() {
    if (!selected) return
    setSubmitted(true)
    if (role === 'werewolf') socket.emit('night:werewolf_vote', selected)
    else if (role === 'seer') socket.emit('night:seer_investigate', selected)
    else if (role === 'doctor') socket.emit('night:doctor_save', selected)
  }

  const canAct = isAlive && !state.nightActionsCompleted && role !== 'villager'

  const selectablePlayers = alivePlayers.filter(p => {
    if (p.id === state.myId) return role === 'doctor'
    if (role === 'werewolf') return !state.werewolfTeammates?.includes(p.id)
    return true
  })

  return (
    <div className="flex flex-col lg:flex-row gap-4 h-full p-4 max-w-5xl mx-auto w-full">
      <div className="flex-1 flex flex-col gap-4">
        <div className="bg-slate-900 border border-slate-700 rounded-xl p-4">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-lg">🌙</span>
            <h2 className="font-bold text-slate-100">Night {state.round}</h2>
          </div>
          <p className="text-slate-400 text-sm">The village sleeps. Creatures of the night awaken.</p>
        </div>

        {!isAlive && (
          <div className="bg-slate-900 border border-slate-700 rounded-xl p-4 text-center">
            <p className="text-slate-400">You are dead. Watch quietly as the night unfolds.</p>
          </div>
        )}

        {isAlive && role === 'villager' && (
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 text-center">
            <p className="text-4xl mb-3">😴</p>
            <p className="text-slate-300 font-medium">You are sleeping…</p>
            <p className="text-slate-500 text-sm mt-1">Waiting for the night to end</p>
          </div>
        )}

        {canAct && (
          <div className="bg-slate-900 border border-slate-700 rounded-xl p-4 flex flex-col gap-3">
            <p className="text-sm font-medium text-slate-300">{role && rolePrompt[role]}</p>
            <PlayerList
              players={selectablePlayers}
              myId={state.myId}
              onSelect={setSelected}
              selectedId={selected ?? undefined}
              selectable
              excludeId={role !== 'doctor' ? state.myId : undefined}
            />
            <Button
              disabled={!selected || submitted}
              loading={submitted}
              onClick={handleAction}
              variant={role === 'werewolf' ? 'danger' : 'primary'}
              className="w-full"
            >
              {role === 'werewolf' ? 'Vote to kill' : role === 'seer' ? 'Investigate' : 'Protect'}
            </Button>
          </div>
        )}

        {state.nightActionsCompleted && isAlive && role !== 'villager' && (
          <div className="bg-slate-900 border border-emerald-800 rounded-xl p-4 text-center">
            <p className="text-emerald-400 text-sm">✓ Your action has been submitted. Waiting for others…</p>
          </div>
        )}

        {isWerewolf && (
          <div className="bg-slate-900 border border-red-900 rounded-xl p-3">
            <p className="text-xs text-red-400 font-semibold mb-1">Wolf pack votes</p>
            <div className="space-y-1">
              {state.players.filter(p => p.role === 'werewolf').map(w => (
                <p key={w.id} className="text-xs text-slate-400">
                  {w.name}: {state.aliveWerewolvesVoted?.includes(w.id) ? '✓ voted' : 'waiting…'}
                </p>
              ))}
            </div>
          </div>
        )}
      </div>

      {isWerewolf && isAlive && (
        <div className="w-full lg:w-80 bg-slate-900 border border-red-900 rounded-xl flex flex-col" style={{ height: '360px' }}>
          <div className="p-3 border-b border-red-900">
            <p className="text-xs font-semibold text-red-400 uppercase tracking-wide">Wolf pack chat</p>
          </div>
          <div className="flex-1 min-h-0">
            <Chat
              messages={nightMessages}
              onSend={content => socket.emit('chat:send', content)}
              canSend
              placeholder="Chat with your pack…"
            />
          </div>
        </div>
      )}
    </div>
  )
}
