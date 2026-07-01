'use client'

import { useMemo, useState } from 'react'
import type { EventKind, ParsedGame, TimelineEvent } from '@/lib/review/types'
import { roleBadgeClass, roleLabel } from './roleStyle'

interface Props {
  game: ParsedGame
}

const KIND_META: Record<EventKind, { label: string; icon: string }> = {
  chat: { label: 'Chat', icon: '💬' },
  system: { label: 'System', icon: 'ℹ️' },
  night_action: { label: 'Night actions', icon: '🌙' },
  day_vote: { label: 'Votes', icon: '🗳️' },
  note: { label: 'Notes', icon: '📝' },
}

const ALL_KINDS: EventKind[] = ['chat', 'system', 'night_action', 'day_vote', 'note']

function timeStr(ts: number): string {
  if (!ts) return ''
  return new Date(ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

function describeNightAction(e: TimelineEvent): string {
  const t = e.targetName || 'someone'
  switch (e.content.toUpperCase()) {
    case 'KILL':
      return `targeted ${t} for the kill`
    case 'INVESTIGATE':
      return `investigated ${t}`
    case 'HEAL':
      return `healed ${t}`
    case 'WITCH_KILL':
      return `poisoned ${t}`
    default:
      return `${e.content} → ${t}`
  }
}

function describeDayVote(e: TimelineEvent): string {
  const isMayor = e.content.toUpperCase() === 'MAYOR'
  if (e.targetName.toLowerCase() === 'skip') return 'voted to skip'
  if (isMayor) return `voted for ${e.targetName} as Mayor`
  return `voted to exile ${e.targetName}`
}

function EventRow({ e }: { e: TimelineEvent }) {
  const meta = KIND_META[e.kind]

  if (e.kind === 'system') {
    return (
      <div className="flex items-start gap-2 py-1">
        <span className="text-[10px] text-slate-600 font-mono w-16 shrink-0 pt-0.5">{timeStr(e.timestamp)}</span>
        <p className="text-sm italic text-slate-400">{e.content}</p>
      </div>
    )
  }

  if (e.kind === 'chat') {
    const isNight = e.phase.toUpperCase() === 'NIGHT'
    return (
      <div className="flex items-start gap-2 py-1">
        <span className="text-[10px] text-slate-600 font-mono w-16 shrink-0 pt-0.5">{timeStr(e.timestamp)}</span>
        <div className="min-w-0">
          <span className={`text-xs px-1.5 py-0.5 rounded border mr-2 ${roleBadgeClass(e.playerRole)}`}>
            {e.playerName}
          </span>
          {isNight && <span className="text-[10px] text-indigo-400 mr-1" title="werewolf night chat">🐺</span>}
          <span className="text-sm text-slate-200 break-words">{e.content}</span>
        </div>
      </div>
    )
  }

  // night_action / day_vote / note
  const body =
    e.kind === 'night_action'
      ? describeNightAction(e)
      : e.kind === 'day_vote'
        ? describeDayVote(e)
        : e.content

  return (
    <div className="flex items-start gap-2 py-1">
      <span className="text-[10px] text-slate-600 font-mono w-16 shrink-0 pt-0.5">{timeStr(e.timestamp)}</span>
      <p className="text-sm text-slate-400">
        <span className="mr-1 select-none">{meta.icon}</span>
        <span className={`font-semibold ${e.kind === 'note' ? 'text-slate-300' : 'text-slate-300'}`}>{e.playerName}</span>
        {e.playerRole && <span className="text-[10px] text-slate-500"> ({roleLabel(e.playerRole)})</span>}
        {e.kind === 'note' ? <span className="text-slate-400">’s note: {body}</span> : <span> {body}</span>}
      </p>
    </div>
  )
}

export default function Timeline({ game }: Props) {
  const [active, setActive] = useState<Set<EventKind>>(new Set(ALL_KINDS))

  const toggle = (k: EventKind) => {
    setActive(prev => {
      const next = new Set(prev)
      if (next.has(k)) next.delete(k)
      else next.add(k)
      return next
    })
  }

  const counts = useMemo(() => {
    const c: Record<EventKind, number> = { chat: 0, system: 0, night_action: 0, day_vote: 0, note: 0 }
    for (const e of game.events) c[e.kind]++
    return c
  }, [game.events])

  const byRound = useMemo(() => {
    const map = new Map<number, TimelineEvent[]>()
    for (const e of game.events) {
      if (!active.has(e.kind)) continue
      const arr = map.get(e.round) ?? []
      arr.push(e)
      map.set(e.round, arr)
    }
    return [...map.entries()].sort((a, b) => a[0] - b[0])
  }, [game.events, active])

  return (
    <div>
      <div className="flex flex-wrap gap-2 mb-4">
        {ALL_KINDS.map(k => {
          const on = active.has(k)
          return (
            <button
              key={k}
              onClick={() => toggle(k)}
              className={`text-xs px-2.5 py-1 rounded-full border transition-colors cursor-pointer ${
                on
                  ? 'border-violet-600 bg-violet-950/40 text-violet-200'
                  : 'border-slate-700 text-slate-500 hover:text-slate-300'
              }`}
            >
              {KIND_META[k].icon} {KIND_META[k].label} ({counts[k]})
            </button>
          )
        })}
      </div>

      {byRound.length === 0 ? (
        <p className="text-slate-500 text-sm py-10 text-center">No events match the current filters.</p>
      ) : (
        <div className="space-y-5">
          {byRound.map(([round, events]) => (
            <section key={round} className="rounded-xl border border-slate-800 bg-slate-900/30">
              <header className="px-4 py-2 border-b border-slate-800 sticky top-0 bg-slate-900/80 backdrop-blur rounded-t-xl">
                <span className="text-sm font-semibold text-slate-200">Round {round}</span>
                <span className="text-xs text-slate-500 ml-2">{events.length} events</span>
              </header>
              <div className="px-4 py-2 divide-y divide-slate-800/60">
                {events.map((e, i) => (
                  <EventRow key={`${round}-${i}-${e.timestamp}`} e={e} />
                ))}
              </div>
            </section>
          ))}
        </div>
      )}
    </div>
  )
}
