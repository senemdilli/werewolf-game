'use client'

import { useMemo, useState } from 'react'
import type {
  ClientGameState, LabelSubmitInput,
  TrustDimension, Confidence, LabelCheckpoint,
} from '@/types/game'
import type { GameSocket } from '@/app/room/[code]/page'

interface Props {
  socket: GameSocket
  state: ClientGameState
}

const DIMENSIONS: { key: TrustDimension; label: string; hint: string }[] = [
  { key: 'alignment', label: 'Alignment', hint: 'On my team?' },
  { key: 'information', label: 'Information', hint: 'Reliable claims?' },
  { key: 'consistency', label: 'Consistency', hint: 'Coherent over time?' },
]

const CONFIDENCES: { key: Confidence; label: string }[] = [
  { key: 'low', label: 'Low' },
  { key: 'medium', label: 'Med' },
  { key: 'high', label: 'High' },
]

const CHECKPOINT_TITLES: Record<LabelCheckpoint, string> = {
  before_discussion: 'Before discussion',
  before_voting: 'Before voting',
  after_voting: 'After voting',
}

type DimUpdate = { score: number; confidence: Confidence }
type TargetState = {
  reasoning: string
  updates: Partial<Record<TrustDimension, DimUpdate>>
}

export default function LabelPanel({ socket, state }: Props) {
  const checkpoint = state.labelCheckpoint
  const [targets, setTargets] = useState<Record<string, TargetState>>({})
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Form state resets naturally because GameRoom keys this component by
  // checkpoint + round (a new key → React remounts → fresh useState).

  const candidates = state.players.filter(p => p.isAlive && p.id !== state.myId)

  function toggleTarget(playerId: string) {
    setTargets(prev => {
      const next = { ...prev }
      if (next[playerId]) delete next[playerId]
      else next[playerId] = { reasoning: '', updates: {} }
      return next
    })
  }

  function setReasoning(playerId: string, value: string) {
    setTargets(prev => ({
      ...prev,
      [playerId]: { ...(prev[playerId] ?? { reasoning: '', updates: {} }), reasoning: value },
    }))
  }

  function setDimension(playerId: string, dim: TrustDimension, update: DimUpdate | null) {
    setTargets(prev => {
      const cur = prev[playerId] ?? { reasoning: '', updates: {} }
      const updates = { ...cur.updates }
      if (update === null) delete updates[dim]
      else updates[dim] = update
      return { ...prev, [playerId]: { ...cur, updates } }
    })
  }

  const canSubmit = useMemo(() => {
    if (submitting) return false
    const ids = Object.keys(targets)
    if (ids.length === 0) return false
    for (const id of ids) {
      const t = targets[id]
      if (!t.reasoning.trim()) return false
      const dims = DIMENSIONS.filter(d => t.updates[d.key])
      if (dims.length === 0) return false
    }
    return true
  }, [targets, submitting])

  function handleSubmit() {
    if (!canSubmit) return
    setSubmitting(true)
    setError(null)
    const payload: LabelSubmitInput = {
      targets: Object.entries(targets).map(([playerId, t]) => ({
        playerId,
        reasoning: t.reasoning.trim(),
        updates: DIMENSIONS
          .filter(d => t.updates[d.key])
          .map(d => ({ dimension: d.key, ...(t.updates[d.key] as DimUpdate) })),
      })),
    }
    socket.emit('label:submit', payload, (r) => {
      setSubmitting(false)
      if (!r.success) setError(r.error ?? 'Failed to save')
    })
  }

  function handleSkip() {
    if (submitting) return
    setSubmitting(true)
    setError(null)
    socket.emit('label:skip', (r) => {
      setSubmitting(false)
      if (!r.success) setError(r.error ?? 'Failed to skip')
    })
  }

  if (!checkpoint) return null

  const me = state.players.find(p => p.id === state.myId)
  if (!me?.isAlive) return null

  const title = CHECKPOINT_TITLES[checkpoint]
  const decidedCount = state.labelDecidedCount
  const decidedTotal = state.labelDecidedTotal
  const meDecided = state.labelMeDecided

  return (
    <div className="fixed inset-0 z-40 bg-slate-950/85 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="w-full max-w-2xl max-h-[90vh] bg-slate-900 border border-amber-800/60 rounded-2xl shadow-2xl flex flex-col">
        <div className="flex items-center justify-between px-5 py-3 border-b border-slate-700">
          <div>
            <div className="text-[10px] uppercase tracking-wider text-amber-400 font-semibold">
              🏷️ Trust labeling · Round {state.round}
            </div>
            <div className="text-base font-semibold text-amber-100 mt-0.5">{title}</div>
          </div>
          <div className="text-xs text-slate-400">
            <span className="font-mono text-amber-300">{decidedCount}</span>
            <span className="text-slate-500"> of </span>
            <span className="font-mono">{decidedTotal}</span>
            <span className="text-slate-500"> ready</span>
          </div>
        </div>

        {meDecided ? (
          <div className="flex-1 flex flex-col items-center justify-center px-6 py-10 gap-3">
            <div className="text-3xl">✓</div>
            <div className="text-amber-100 font-semibold">You&apos;re ready.</div>
            <div className="text-sm text-slate-400 text-center">
              Waiting for {decidedTotal - decidedCount} other player{decidedTotal - decidedCount === 1 ? '' : 's'} to finish.
            </div>
          </div>
        ) : (
          <div className="p-5 flex flex-col gap-4 overflow-y-auto">
            <p className="text-sm text-slate-300">
              Label any players whose trustworthiness changed for you. Or hit{' '}
              <span className="text-slate-200 font-semibold">Don&apos;t label</span> to skip this checkpoint.
            </p>

            <div>
              <div className="text-xs text-slate-400 font-semibold mb-1.5">Players</div>
              <div className="flex flex-wrap gap-1.5">
                {candidates.map(p => {
                  const selected = !!targets[p.id]
                  return (
                    <button
                      key={p.id}
                      onClick={() => toggleTarget(p.id)}
                      className={`px-2.5 py-1 rounded text-sm border transition-colors cursor-pointer ${
                        selected
                          ? 'bg-amber-900/60 border-amber-600 text-amber-100'
                          : 'bg-slate-800 border-slate-700 text-slate-300 hover:border-amber-700'
                      }`}
                    >
                      {p.name}
                    </button>
                  )
                })}
              </div>
            </div>

            {Object.keys(targets).map(playerId => {
              const p = state.players.find(pp => pp.id === playerId)
              if (!p) return null
              const t = targets[playerId]
              return (
                <div key={playerId} className="border border-slate-700 rounded-lg p-3 bg-slate-800/40 flex flex-col gap-3">
                  <div className="text-sm text-amber-200 font-semibold">{p.name}</div>

                  <div>
                    <label className="text-[10px] uppercase tracking-wide text-slate-500 font-semibold">
                      Reasoning
                    </label>
                    <textarea
                      value={t.reasoning}
                      onChange={e => setReasoning(playerId, e.target.value)}
                      placeholder={`Why did your trust in ${p.name} change?`}
                      maxLength={2000}
                      rows={2}
                      className="w-full mt-1 bg-slate-800 border border-slate-700 rounded px-2.5 py-1.5 text-sm text-slate-100 placeholder-slate-500 resize-none focus:outline-none focus:border-amber-600"
                    />
                  </div>

                  <div className="flex flex-col gap-2">
                    {DIMENSIONS.map(d => {
                      const cur = t.updates[d.key]
                      const on = !!cur
                      return (
                        <div key={d.key} className="flex flex-col gap-1">
                          <button
                            onClick={() =>
                              setDimension(playerId, d.key, on ? null : { score: 4, confidence: 'medium' })
                            }
                            className={`text-xs text-left px-2 py-1 rounded border cursor-pointer ${
                              on
                                ? 'bg-amber-950/40 border-amber-700 text-amber-200'
                                : 'bg-slate-800 border-slate-700 text-slate-400 hover:border-amber-800'
                            }`}
                          >
                            {on ? '✓' : '+'} {d.label} <span className="text-slate-500">— {d.hint}</span>
                          </button>
                          {on && (
                            <div className="pl-2 flex flex-col gap-1.5">
                              <div className="flex flex-col gap-0.5">
                                <div className="text-[10px] uppercase tracking-wide text-slate-500 font-semibold">
                                  Score <span className="text-slate-600 normal-case">(1 = low trust · 7 = high)</span>
                                </div>
                                <div className="grid grid-cols-7 gap-0.5">
                                  {[1, 2, 3, 4, 5, 6, 7].map(n => (
                                    <button
                                      key={n}
                                      onClick={() => setDimension(playerId, d.key, { ...cur, score: n })}
                                      className={`py-0.5 rounded text-xs font-mono cursor-pointer ${
                                        cur.score === n
                                          ? 'bg-amber-700 text-amber-50'
                                          : 'bg-slate-800 text-slate-400 hover:bg-slate-700'
                                      }`}
                                    >
                                      {n}
                                    </button>
                                  ))}
                                </div>
                              </div>
                              <div className="flex flex-col gap-0.5">
                                <div className="text-[10px] uppercase tracking-wide text-slate-500 font-semibold">
                                  Confidence
                                </div>
                                <div className="flex gap-1">
                                  {CONFIDENCES.map(c => (
                                    <button
                                      key={c.key}
                                      onClick={() => setDimension(playerId, d.key, { ...cur, confidence: c.key })}
                                      className={`flex-1 py-0.5 rounded text-xs cursor-pointer ${
                                        cur.confidence === c.key
                                          ? 'bg-amber-800 text-amber-100'
                                          : 'bg-slate-800 text-slate-400 hover:bg-slate-700'
                                      }`}
                                    >
                                      {c.label}
                                    </button>
                                  ))}
                                </div>
                              </div>
                            </div>
                          )}
                        </div>
                      )
                    })}
                  </div>
                </div>
              )
            })}

            {error && (
              <div className="text-xs text-red-300 bg-red-950/40 border border-red-800 rounded px-2 py-1">
                {error}
              </div>
            )}

            <div className="flex gap-2 pt-1">
              <button
                onClick={handleSkip}
                disabled={submitting}
                className="flex-1 py-2.5 bg-slate-800 hover:bg-slate-700 disabled:opacity-50 border border-slate-700 text-slate-200 text-sm font-semibold rounded transition-colors cursor-pointer"
              >
                Don&apos;t label
              </button>
              <button
                onClick={handleSubmit}
                disabled={!canSubmit}
                className="flex-1 py-2.5 bg-amber-700 hover:bg-amber-600 disabled:bg-slate-700 disabled:text-slate-500 text-amber-50 text-sm font-semibold rounded transition-colors cursor-pointer"
              >
                {submitting ? 'Saving…' : 'Save labels'}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
