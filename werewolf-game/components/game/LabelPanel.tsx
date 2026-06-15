'use client'

import { useEffect, useMemo, useRef, useState } from 'react'
import type {
  ClientGameState, LabelSubmitInput,
  TrustDimension, Confidence, LabelCheckpoint,
} from '@/types/game'
import type { GameSocket } from '@/app/room/[code]/page'

interface Props {
  socket: GameSocket
  state: ClientGameState
}

const DIMENSIONS: { key: TrustDimension; label: string; question: string }[] = [
  {
    key: 'alignment',
    label: 'Alignment trust',
    question: 'Do I believe this player’s goals are compatible with mine?',
  },
  {
    key: 'information',
    label: 'Information trust',
    question: 'Do I believe this player gives accurate or useful information?',
  },
  {
    key: 'consistency',
    label: 'Consistency trust',
    question: 'Do I believe this player behaves predictably over time?',
  },
]

const CONFIDENCES: { key: Confidence; label: string }[] = [
  { key: 'low', label: 'Low' },
  { key: 'medium', label: 'Med' },
  { key: 'high', label: 'High' },
]

const SCORE_LABELS: Record<number, string> = {
  1: 'Strong distrust',
  2: 'Distrust',
  3: 'Slight distrust',
  4: 'Neutral',
  5: 'Slight trust',
  6: 'Trust',
  7: 'Strong trust',
}

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

  // Voice input state (per-target Deepgram streaming).
  const [speechLanguage, setSpeechLanguage] = useState<'en' | 'de'>('en')
  const [isRecording, setIsRecording] = useState<Record<string, boolean>>({})
  const mediaRecorderRef = useRef<Record<string, MediaRecorder>>({})
  const wsRef = useRef<Record<string, WebSocket | null>>({})
  const currentInterimRef = useRef<Record<string, string>>({})
  const streamsRef = useRef<Record<string, MediaStream>>({})
  const audioChunksRef = useRef<Record<string, Blob[]>>({})
  const useFallbackRef = useRef<Record<string, boolean>>({})
  const silenceTimeoutRef = useRef<Record<string, ReturnType<typeof setTimeout> | null>>({})

  // Form state resets naturally because GameRoom keys this component by
  // checkpoint + round (a new key → React remounts → fresh useState).

  // Tear down any live media when the modal unmounts (between checkpoints,
  // or when the round ends).
  useEffect(() => {
    const recorders = mediaRecorderRef.current
    const sockets = wsRef.current
    const streams = streamsRef.current
    const timers = silenceTimeoutRef.current
    return () => {
      for (const r of Object.values(recorders)) { try { r?.stop() } catch { /* noop */ } }
      for (const s of Object.values(sockets)) { try { s?.close() } catch { /* noop */ } }
      for (const s of Object.values(streams)) {
        try { s?.getTracks().forEach(t => t.stop()) } catch { /* noop */ }
      }
      for (const t of Object.values(timers)) { if (t) clearTimeout(t) }
    }
  }, [])

  // Cross-component handshake: when Chat starts its own recording it dispatches
  // 'stop-all-recordings', and vice versa. Keeps only one mic live at a time.
  useEffect(() => {
    const handler = () => {
      Object.keys(isRecording).forEach(playerId => {
        if (isRecording[playerId]) stopRecording(playerId)
      })
    }
    window.addEventListener('stop-all-recordings', handler)
    return () => window.removeEventListener('stop-all-recordings', handler)
  }, [isRecording])

  const candidates = state.players.filter(p => p.isAlive && p.id !== state.myId)

  function toggleTarget(playerId: string) {
    setTargets(prev => {
      const next = { ...prev }
      if (next[playerId]) {
        delete next[playerId]
        // Deselecting a target: end any live mic for them.
        if (isRecording[playerId]) stopRecording(playerId)
      } else {
        next[playerId] = { reasoning: '', updates: {} }
      }
      return next
    })
  }

  function setReasoning(playerId: string, value: string) {
    setTargets(prev => ({
      ...prev,
      [playerId]: { ...(prev[playerId] ?? { reasoning: '', updates: {} }), reasoning: value },
    }))
  }

  // Append text into a target's reasoning, optionally trimming the previous
  // interim chunk first. Used by both interim and final transcript events.
  function patchReasoning(
    playerId: string,
    update: (current: string) => string,
  ) {
    setTargets(prev => {
      const cur = prev[playerId] ?? { reasoning: '', updates: {} }
      return { ...prev, [playerId]: { ...cur, reasoning: update(cur.reasoning) } }
    })
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

  function resetSilenceTimer(playerId: string) {
    const existing = silenceTimeoutRef.current[playerId]
    if (existing) clearTimeout(existing)
    silenceTimeoutRef.current[playerId] = setTimeout(() => stopRecording(playerId), 6000)
  }

  async function transcribeHttpAudio(playerId: string) {
    setIsRecording(prev => ({ ...prev, [playerId]: false }))

    const stream = streamsRef.current[playerId]
    if (stream) {
      try { stream.getTracks().forEach(t => t.stop()) } catch { /* noop */ }
      delete streamsRef.current[playerId]
    }

    const chunks = audioChunksRef.current[playerId]
    if (!chunks || chunks.length === 0) return
    const recorder = mediaRecorderRef.current[playerId]
    const blob = new Blob(chunks, { type: recorder?.mimeType || 'audio/webm' })

    patchReasoning(playerId, cur => `${cur}${cur ? ' ' : ''}🎙️ [Transcribing...]`)

    try {
      const res = await fetch('/api/speech-to-text', {
        method: 'POST',
        headers: {
          'Content-Type': recorder?.mimeType || 'audio/webm',
          'X-Speech-Language': speechLanguage,
        },
        body: blob,
      })
      const data = await res.json()
      patchReasoning(playerId, cur => {
        const cleaned = cur.replace('🎙️ [Transcribing...]', '').trim()
        if (data.transcript) return (cleaned + (cleaned ? ' ' : '') + data.transcript).trim()
        if (data.error) setError(`Transcription error: ${data.error}`)
        return cleaned
      })
    } catch (err) {
      console.error(err)
      setError('Failed to contact speech-to-text service')
      patchReasoning(playerId, cur => cur.replace('🎙️ [Transcribing...]', '').trim())
    }
  }

  async function startHttpRecording(playerId: string) {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      streamsRef.current[playerId] = stream
      let mediaRecorder: MediaRecorder
      try {
        mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm' })
      } catch {
        mediaRecorder = new MediaRecorder(stream)
      }
      audioChunksRef.current[playerId] = []
      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) audioChunksRef.current[playerId].push(e.data)
      }
      mediaRecorder.onstop = () => transcribeHttpAudio(playerId)
      mediaRecorderRef.current[playerId] = mediaRecorder
      mediaRecorder.start()
      setIsRecording(prev => ({ ...prev, [playerId]: true }))
    } catch (err) {
      console.error(err)
      setError('Could not access microphone.')
    }
  }

  async function startRecording(playerId: string) {
    try {
      setError(null)
      currentInterimRef.current[playerId] = ''
      audioChunksRef.current[playerId] = []
      useFallbackRef.current[playerId] = false

      // Only one mic at a time across the page.
      window.dispatchEvent(new CustomEvent('stop-all-recordings'))

      let token = ''
      try {
        const tokenRes = await fetch('/api/speech-token')
        const tokenData = await tokenRes.json()
        token = tokenData.token
      } catch (e) {
        console.error('Failed to get token, falling back to HTTP', e)
        useFallbackRef.current[playerId] = true
      }

      if (useFallbackRef.current[playerId] || !token) {
        await startHttpRecording(playerId)
        return
      }

      const wsUrl = `wss://api.deepgram.com/v1/listen?model=nova-3&smart_format=true&interim_results=true&language=${speechLanguage}&numerals=true`
      const ws = new WebSocket(wsUrl, ['token', token])
      wsRef.current[playerId] = ws

      ws.onopen = async () => {
        resetSilenceTimer(playerId)
        try {
          const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
          streamsRef.current[playerId] = stream
          let mediaRecorder: MediaRecorder
          try {
            mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm' })
          } catch {
            mediaRecorder = new MediaRecorder(stream)
          }
          mediaRecorder.ondataavailable = (event) => {
            if (event.data.size > 0) {
              audioChunksRef.current[playerId].push(event.data)
              if (ws.readyState === WebSocket.OPEN && !useFallbackRef.current[playerId]) {
                ws.send(event.data)
              }
            }
          }
          mediaRecorder.onstop = () => {
            if (ws.readyState === WebSocket.OPEN && !useFallbackRef.current[playerId]) {
              ws.send(JSON.stringify({ type: 'CloseStream' }))
            }
          }
          mediaRecorderRef.current[playerId] = mediaRecorder
          mediaRecorder.start(100)
          setIsRecording(prev => ({ ...prev, [playerId]: true }))
        } catch (err) {
          console.error('Error starting MediaRecorder:', err)
          setError('Microphone access denied.')
          ws.close()
        }
      }

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          const transcript: string = data.channel?.alternatives?.[0]?.transcript || ''
          if (!transcript.trim()) return
          resetSilenceTimer(playerId)
          const isFinal: boolean = !!data.is_final
          patchReasoning(playerId, cur => {
            const oldInterim = currentInterimRef.current[playerId] || ''
            let base = cur
            if (oldInterim && base.endsWith(oldInterim)) {
              base = base.substring(0, base.length - oldInterim.length).trim()
            }
            if (isFinal) {
              currentInterimRef.current[playerId] = ''
              return base + (base ? ' ' : '') + transcript.trim()
            }
            const interimStr = ' ' + transcript.trim()
            currentInterimRef.current[playerId] = interimStr
            return base + interimStr
          })
        } catch (e) {
          console.error('Error parsing WebSocket message:', e)
        }
      }

      ws.onerror = (err) => {
        console.warn('WebSocket failed (firewall/VPN/scopes), using HTTP fallback...', err)
        useFallbackRef.current[playerId] = true
      }

      ws.onclose = () => {
        const t = silenceTimeoutRef.current[playerId]
        if (t) { clearTimeout(t); silenceTimeoutRef.current[playerId] = null }

        if (useFallbackRef.current[playerId]) {
          transcribeHttpAudio(playerId)
          return
        }
        setIsRecording(prev => ({ ...prev, [playerId]: false }))
        // Drop any lingering interim text.
        patchReasoning(playerId, cur => {
          const oldInterim = currentInterimRef.current[playerId] || ''
          if (oldInterim && cur.endsWith(oldInterim)) {
            return cur.substring(0, cur.length - oldInterim.length).trim()
          }
          return cur
        })
        currentInterimRef.current[playerId] = ''
        const stream = streamsRef.current[playerId]
        if (stream) {
          try { stream.getTracks().forEach(t => t.stop()) } catch { /* noop */ }
          delete streamsRef.current[playerId]
        }
      }
    } catch (err) {
      console.error(err)
      setError('Real-time connection failed. Falling back to HTTP...')
      await startHttpRecording(playerId)
    }
  }

  function stopRecording(playerId: string) {
    const t = silenceTimeoutRef.current[playerId]
    if (t) { clearTimeout(t); silenceTimeoutRef.current[playerId] = null }
    const recorder = mediaRecorderRef.current[playerId]
    if (recorder) { try { recorder.stop() } catch { /* noop */ } }
    const ws = wsRef.current[playerId]
    if (ws) { try { ws.close() } catch { /* noop */ } }
  }

  function toggleSpeechRecording(playerId: string) {
    if (isRecording[playerId]) stopRecording(playerId)
    else startRecording(playerId)
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
              const recording = !!isRecording[playerId]
              return (
                <div key={playerId} className="border border-slate-700 rounded-lg p-3 bg-slate-800/40 flex flex-col gap-3">
                  <div className="text-sm text-amber-200 font-semibold">{p.name}</div>

                  <div>
                    <div className="flex items-center justify-between mb-1">
                      <label className="text-[10px] uppercase tracking-wide text-slate-500 font-semibold">
                        Reasoning {recording && <span className="text-red-400 normal-case animate-pulse ml-2">(Live recording...)</span>}
                      </label>
                      <div className="flex items-center gap-1.5">
                        <div className="flex bg-slate-900 border border-slate-800 rounded p-0.5 text-[9px] font-semibold text-slate-400">
                          <button
                            type="button"
                            onClick={() => setSpeechLanguage('en')}
                            disabled={recording}
                            className={`px-1.5 py-0.5 rounded transition-all ${
                              speechLanguage === 'en'
                                ? 'bg-amber-950/40 border border-amber-900/60 text-amber-200'
                                : recording
                                  ? 'opacity-30 cursor-not-allowed text-slate-600'
                                  : 'cursor-pointer hover:text-slate-200'
                            }`}
                          >
                            EN
                          </button>
                          <button
                            type="button"
                            onClick={() => setSpeechLanguage('de')}
                            disabled={recording}
                            className={`px-1.5 py-0.5 rounded transition-all ${
                              speechLanguage === 'de'
                                ? 'bg-amber-950/40 border border-amber-900/60 text-amber-200'
                                : recording
                                  ? 'opacity-30 cursor-not-allowed text-slate-600'
                                  : 'cursor-pointer hover:text-slate-200'
                            }`}
                          >
                            DE
                          </button>
                        </div>

                        <button
                          type="button"
                          onClick={() => toggleSpeechRecording(playerId)}
                          className={`flex items-center gap-1.5 text-xs px-2.5 py-1 rounded cursor-pointer transition-all duration-200 ${
                            recording
                              ? 'bg-red-950 border border-red-800 text-red-400 font-semibold animate-pulse scale-105'
                              : 'bg-slate-800 border border-slate-700 text-slate-300 hover:text-amber-300 hover:border-amber-700/60'
                          }`}
                          title={recording ? 'Stop voice recording' : `Speak reasoning in ${speechLanguage === 'en' ? 'English' : 'German'}`}
                        >
                          {recording ? (
                            <>
                              <span className="w-2 h-2 rounded-full bg-red-500 animate-ping inline-block" />
                              <span>Stop</span>
                            </>
                          ) : (
                            <>
                              <span className="text-sm">🎙️</span>
                              <span>Voice</span>
                            </>
                          )}
                        </button>
                      </div>
                    </div>
                    <textarea
                      value={t.reasoning}
                      onChange={e => setReasoning(playerId, e.target.value)}
                      placeholder={`Why did your trust in ${p.name} change?`}
                      maxLength={2000}
                      rows={3}
                      className={`w-full bg-slate-800 border rounded px-2.5 py-1.5 text-sm text-slate-100 placeholder-slate-500 resize-none focus:outline-none ${
                        recording
                          ? 'border-red-500/80 shadow-[0_0_8px_rgba(239,68,68,0.2)] animate-pulse'
                          : 'border-slate-700 focus:border-amber-600'
                      }`}
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
                            className={`text-xs text-left px-2 py-1.5 rounded border cursor-pointer ${
                              on
                                ? 'bg-amber-950/40 border-amber-700 text-amber-200'
                                : 'bg-slate-800 border-slate-700 text-slate-400 hover:border-amber-800'
                            }`}
                          >
                            <div className="font-semibold">{on ? '✓' : '+'} {d.label}</div>
                            <div className="text-[11px] text-slate-500 mt-0.5 leading-snug">{d.question}</div>
                          </button>
                          {on && (
                            <div className="pl-2 flex flex-col gap-1.5">
                              <div className="flex flex-col gap-0.5">
                                <div className="text-[10px] uppercase tracking-wide text-slate-500 font-semibold flex items-center justify-between gap-2">
                                  <span>Score</span>
                                  <span className="text-amber-300/80 normal-case font-semibold tracking-normal">
                                    {cur.score} — {SCORE_LABELS[cur.score]}
                                  </span>
                                </div>
                                <div className="grid grid-cols-7 gap-0.5">
                                  {[1, 2, 3, 4, 5, 6, 7].map(n => (
                                    <button
                                      key={n}
                                      onClick={() => setDimension(playerId, d.key, { ...cur, score: n })}
                                      title={`${n} — ${SCORE_LABELS[n]}`}
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
