'use client'

import { useEffect, useMemo, useState } from 'react'
import type { LabelScore, LabelTarget, ParsedLabels, TrustDimension } from '@/lib/review/types'
import { roleBadgeClass, roleLabel, scoreClass, confidenceLabel } from './roleStyle'

interface Props {
  labels: ParsedLabels
}

const DIMENSIONS: { key: TrustDimension; short: string; label: string }[] = [
  { key: 'alignment', short: 'A', label: 'Alignment' },
  { key: 'information', short: 'I', label: 'Information' },
  { key: 'consistency', short: 'C', label: 'Consistency' },
]

function checkpointLabel(cp: string): string {
  return cp
    .toLowerCase()
    .split('_')
    .map((w, i) => (i === 0 ? w.charAt(0).toUpperCase() + w.slice(1) : w))
    .join(' ')
}

function ScoreChip({ short, score }: { short: string; score: LabelScore | undefined }) {
  if (!score) {
    return (
      <span className="text-[10px] px-1.5 py-0.5 rounded border border-slate-800 text-slate-600" title="not scored">
        {short} —
      </span>
    )
  }
  return (
    <span
      className={`text-[10px] px-1.5 py-0.5 rounded border font-mono ${scoreClass(score.score)}`}
      title={`${short}: ${score.score}/7, confidence ${confidenceLabel(score.confidence)}`}
    >
      {short} {score.score}/7
      <span className="opacity-60"> · {confidenceLabel(score.confidence).charAt(0)}</span>
    </span>
  )
}

function TargetRow({ target }: { target: LabelTarget }) {
  return (
    <div className="py-2 border-t border-slate-800/60 first:border-t-0">
      <div className="flex flex-wrap items-center gap-2">
        <span className={`text-xs px-1.5 py-0.5 rounded border ${roleBadgeClass(target.player.role)}`}>
          {target.player.name}
        </span>
        <ScoreChip short="A" score={target.alignment} />
        <ScoreChip short="I" score={target.information} />
        <ScoreChip short="C" score={target.consistency} />
      </div>
      {target.reasoning && <p className="mt-1.5 text-sm text-slate-300 leading-snug">{target.reasoning}</p>}
    </div>
  )
}

export default function TrustLabels({ labels }: Props) {
  const rounds = useMemo(() => labels.rounds.map(r => r.round), [labels.rounds])
  const [round, setRound] = useState<number | null>(rounds[0] ?? null)

  const roundData = useMemo(() => labels.rounds.find(r => r.round === round) ?? null, [labels.rounds, round])
  const checkpoints = roundData?.checkpoints ?? []
  const [checkpoint, setCheckpoint] = useState<string | null>(checkpoints[0]?.checkpoint ?? null)

  // Keep the checkpoint selection valid whenever the round changes.
  useEffect(() => {
    const cps = roundData?.checkpoints ?? []
    if (!cps.some(c => c.checkpoint === checkpoint)) {
      setCheckpoint(cps[0]?.checkpoint ?? null)
    }
  }, [roundData, checkpoint])

  const activeCheckpoint = checkpoints.find(c => c.checkpoint === checkpoint) ?? null

  if (labels.rounds.length === 0) {
    return <p className="text-slate-500 text-sm py-10 text-center">This labels file has no recorded labels.</p>
  }

  return (
    <div>
      {/* Legend */}
      <div className="flex flex-wrap items-center gap-3 mb-4 text-[11px] text-slate-500">
        <span>Trust dimensions:</span>
        {DIMENSIONS.map(d => (
          <span key={d.key}>
            <span className="font-mono text-slate-300">{d.short}</span> = {d.label}
          </span>
        ))}
        <span className="ml-auto">score 1–7 · confidence l/m/h</span>
      </div>

      {/* Round selector */}
      <div className="flex flex-wrap gap-2 mb-3">
        {rounds.map(r => (
          <button
            key={r}
            onClick={() => setRound(r)}
            className={`text-xs px-3 py-1 rounded-full border transition-colors cursor-pointer ${
              r === round
                ? 'border-violet-600 bg-violet-950/40 text-violet-200'
                : 'border-slate-700 text-slate-500 hover:text-slate-300'
            }`}
          >
            Round {r}
          </button>
        ))}
      </div>

      {/* Checkpoint selector */}
      <div className="flex flex-wrap gap-2 mb-5">
        {checkpoints.map(c => (
          <button
            key={c.checkpoint}
            onClick={() => setCheckpoint(c.checkpoint)}
            className={`text-xs px-3 py-1 rounded border transition-colors cursor-pointer ${
              c.checkpoint === checkpoint
                ? 'border-emerald-700 bg-emerald-950/40 text-emerald-200'
                : 'border-slate-700 text-slate-500 hover:text-slate-300'
            }`}
          >
            {checkpointLabel(c.checkpoint)}
            <span className="opacity-60 ml-1">({c.labels.length})</span>
          </button>
        ))}
      </div>

      {!activeCheckpoint || activeCheckpoint.labels.length === 0 ? (
        <p className="text-slate-500 text-sm py-10 text-center">No labels recorded at this checkpoint.</p>
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {activeCheckpoint.labels.map(entry => (
            <div key={entry.id} className="rounded-xl border border-slate-800 bg-slate-900/30 p-4">
              <div className="flex items-center gap-2 mb-2">
                <span className="text-[10px] uppercase tracking-wider text-slate-500">Observer</span>
                <span className={`text-xs px-1.5 py-0.5 rounded border ${roleBadgeClass(entry.observer.role)}`}>
                  {entry.observer.name}
                </span>
                <span className="text-[10px] text-slate-500">{roleLabel(entry.observer.role)}</span>
              </div>
              {entry.targets.map((t, i) => (
                <TargetRow key={`${entry.id}-${t.player.id}-${i}`} target={t} />
              ))}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
