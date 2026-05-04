'use client'

import type { ClientGameState, Role } from '@/types/game'
import { ROLE_INFO } from '@/server/game/roles'
import Button from '@/components/ui/Button'

const roleStyle: Record<Role, { border: string; bg: string; icon: string }> = {
  werewolf: { border: 'border-red-700',    bg: 'bg-red-950/40',    icon: '🐺' },
  villager: { border: 'border-blue-700',   bg: 'bg-blue-950/40',   icon: '🏘' },
  seer:     { border: 'border-amber-700',  bg: 'bg-amber-950/40',  icon: '🔮' },
  doctor:   { border: 'border-emerald-700', bg: 'bg-emerald-950/40', icon: '⚕' },
}

interface Props {
  state: ClientGameState
  onAcknowledge: () => void
  acknowledged: boolean
}

export default function RoleReveal({ state, onAcknowledge, acknowledged }: Props) {
  const role = state.myRole
  if (!role) return null

  const info = ROLE_INFO[role]
  const style = roleStyle[role]
  const teammates = state.werewolfTeammates
  const teammateNames = teammates
    ? state.players.filter(p => teammates.includes(p.id)).map(p => p.name)
    : []

  const pending = state.players.filter(p => {
    const full = state.players.find(pl => pl.id === p.id)
    return full?.isAlive
  })

  return (
    <div className="flex flex-col items-center justify-center min-h-screen px-4">
      <div className={`w-full max-w-sm border ${style.border} ${style.bg} rounded-2xl p-8 text-center animate-fade-in`}>
        <div className="text-6xl mb-4">{style.icon}</div>
        <h1 className="text-2xl font-bold mb-1">You are the</h1>
        <h2 className={`text-3xl font-black mb-4 text-${info.color}-400`}>{info.label}</h2>
        <p className="text-slate-300 text-sm leading-relaxed mb-6">{info.description}</p>

        {role === 'werewolf' && teammateNames.length > 0 && (
          <div className="bg-red-950/60 border border-red-800 rounded-lg p-3 mb-6 text-sm">
            <p className="text-red-300 font-semibold mb-1">Your pack:</p>
            <p className="text-red-200">{teammateNames.join(', ')}</p>
          </div>
        )}

        <Button
          className="w-full"
          variant={acknowledged ? 'ghost' : 'primary'}
          disabled={acknowledged}
          onClick={onAcknowledge}
        >
          {acknowledged ? 'Waiting for others…' : 'I understand my role'}
        </Button>

        <p className="text-slate-500 text-xs mt-3">
          {state.players.filter(p => p.isAlive).length - (acknowledged ? 0 : 0)} players ready
        </p>
      </div>
    </div>
  )
}
