'use client'

import { useCallback, useRef, useState } from 'react'
import { classifyFile, parseGameCsv, parseLabelsJson } from '@/lib/review/parse'
import type { ParsedGame, ParsedLabels } from '@/lib/review/types'
import GameSummary from '@/components/review/GameSummary'
import Timeline from '@/components/review/Timeline'
import TrustLabels from '@/components/review/TrustLabels'

type Tab = 'timeline' | 'labels'

export default function ReviewPage() {
  const [game, setGame] = useState<ParsedGame | null>(null)
  const [labels, setLabels] = useState<ParsedLabels | null>(null)
  const [tab, setTab] = useState<Tab>('timeline')
  const [errors, setErrors] = useState<string[]>([])
  const [dragOver, setDragOver] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  const handleFiles = useCallback(async (fileList: FileList | File[]) => {
    const files = Array.from(fileList)
    if (files.length === 0) return
    const nextErrors: string[] = []
    let nextGame: ParsedGame | null = null
    let nextLabels: ParsedLabels | null = null

    for (const file of files) {
      const kind = classifyFile(file)
      try {
        const text = await file.text()
        if (kind === 'csv') {
          nextGame = parseGameCsv(text)
        } else if (kind === 'json') {
          nextLabels = parseLabelsJson(text)
        } else {
          nextErrors.push(`Skipped "${file.name}": expected a .csv or .json file.`)
        }
      } catch (err) {
        nextErrors.push(`"${file.name}": ${(err as Error).message}`)
      }
    }

    setErrors(nextErrors)
    // Merge with whatever is already loaded so users can add the labels file
    // in a second drop without losing the game (and vice versa).
    if (nextGame) setGame(nextGame)
    if (nextLabels) setLabels(nextLabels)
    if (nextGame && tab === 'labels' && !nextLabels && !labels) setTab('timeline')
  }, [tab, labels])

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault()
      setDragOver(false)
      if (e.dataTransfer.files?.length) handleFiles(e.dataTransfer.files)
    },
    [handleFiles],
  )

  function reset() {
    setGame(null)
    setLabels(null)
    setErrors([])
    setTab('timeline')
    if (inputRef.current) inputRef.current.value = ''
  }

  const hasContent = game || labels

  return (
    <div className="min-h-screen p-6 max-w-5xl mx-auto">
      <div className="mb-6 flex items-start justify-between">
        <div>
          <a href="/admin" className="text-slate-500 hover:text-slate-300 text-sm">← Back to admin</a>
          <h1 className="text-2xl font-bold text-slate-100 mt-2">Game Review</h1>
          <p className="text-slate-400 text-sm mt-1">
            Load an exported game <span className="font-mono text-slate-300">.csv</span> and its{' '}
            <span className="font-mono text-slate-300">-labels.json</span> to replay it offline.
          </p>
        </div>
        {hasContent && (
          <button
            onClick={reset}
            className="text-xs px-3 py-1.5 bg-slate-800 hover:bg-slate-700 border border-slate-600 rounded transition-colors cursor-pointer text-slate-300"
          >
            Load other files
          </button>
        )}
      </div>

      {/* Dropzone */}
      <div
        onDragOver={e => {
          e.preventDefault()
          setDragOver(true)
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={onDrop}
        onClick={() => inputRef.current?.click()}
        className={`mb-6 rounded-xl border-2 border-dashed p-6 text-center cursor-pointer transition-colors ${
          dragOver ? 'border-violet-500 bg-violet-950/20' : 'border-slate-700 hover:border-slate-600'
        }`}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".csv,.json,application/json,text/csv"
          multiple
          className="hidden"
          onChange={e => e.target.files && handleFiles(e.target.files)}
        />
        <p className="text-slate-300 text-sm">
          Drop the <span className="font-mono">.csv</span> and{' '}
          <span className="font-mono">-labels.json</span> here, or click to browse.
        </p>
        <p className="text-slate-600 text-xs mt-1">You can drop both at once, or add them one at a time.</p>
        {hasContent && (
          <p className="text-xs mt-3 text-slate-400">
            Loaded: {game ? <span className="text-emerald-400">CSV ✓</span> : <span className="text-slate-600">CSV —</span>}
            {'  ·  '}
            {labels ? <span className="text-emerald-400">labels ✓</span> : <span className="text-slate-600">labels —</span>}
          </p>
        )}
      </div>

      {errors.length > 0 && (
        <div className="mb-6 rounded-lg border border-red-900 bg-red-950/30 p-3">
          {errors.map((e, i) => (
            <p key={i} className="text-sm text-red-300">{e}</p>
          ))}
        </div>
      )}

      {!hasContent ? (
        <div className="text-slate-600 text-center py-16 text-sm">
          No game loaded yet. Exports come from the admin dashboard&apos;s CSV / JSON buttons.
        </div>
      ) : (
        <div className="space-y-6">
          {game ? (
            <GameSummary game={game} hasLabels={!!labels} />
          ) : (
            <div className="rounded-xl border border-amber-900/60 bg-amber-950/20 p-4 text-sm text-amber-200">
              Labels loaded for <span className="font-mono">{labels?.roomCode}</span>, but no CSV yet — drop the matching{' '}
              <span className="font-mono">.csv</span> to see the timeline.
            </div>
          )}

          {/* Tabs */}
          <div className="flex border-b border-slate-800">
            <button
              onClick={() => setTab('timeline')}
              disabled={!game}
              className={`px-4 py-2 text-sm font-semibold border-b-2 transition-colors cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed ${
                tab === 'timeline' ? 'border-violet-500 text-violet-400' : 'border-transparent text-slate-400 hover:text-slate-200'
              }`}
            >
              Timeline
            </button>
            <button
              onClick={() => setTab('labels')}
              disabled={!labels}
              className={`px-4 py-2 text-sm font-semibold border-b-2 transition-colors cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed ${
                tab === 'labels' ? 'border-violet-500 text-violet-400' : 'border-transparent text-slate-400 hover:text-slate-200'
              }`}
            >
              Trust Labels {labels ? '' : '(none)'}
            </button>
          </div>

          {tab === 'timeline' && game && <Timeline game={game} />}
          {tab === 'labels' && labels && <TrustLabels labels={labels} />}
          {tab === 'timeline' && !game && (
            <p className="text-slate-500 text-sm py-10 text-center">Drop the CSV to view the timeline.</p>
          )}
        </div>
      )}
    </div>
  )
}
