'use client'

import { useEffect, useMemo, useState, useRef } from 'react'
import type {
  ClientGameState, ChatMessage, LabelAction, LabelCreateInput,
  TrustDimension, Confidence, Phase,
} from '@/types/game'
import { LABEL_ACTIONS } from '@/types/game'

const DAY_LIKE_PHASES = new Set<Phase>([
  'mayor_advocacy', 'mayor_election', 'day_discussion', 'day_vote', 'day_result',
])
import type { GameSocket } from '@/app/room/[code]/page'

interface Props {
  socket: GameSocket
  state: ClientGameState
  messages: ChatMessage[]
  autoOpenTrigger: string | null  // a system message id that should auto-open + preselect
}

const ACTION_LABELS: Record<LabelAction, string> = {
  voted_to_exile: 'Voted to exile',
  voted_for_mayor: 'Voted for mayor',
  accused_of_werewolf: 'Accused of being a werewolf',
  accused_of_lying: 'Accused of lying',
  claimed_role: 'Claimed a role',
  defended: 'Defended someone',
  supported: 'Supported someone',
  betrayed: 'Betrayed someone',
  contradicted_themselves: 'Contradicted themselves',
  did_not_respond: 'Did not respond',
  other: 'Other',
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

type DimUpdate = { score: number; confidence: Confidence }
type TargetUpdates = Partial<Record<TrustDimension, DimUpdate>>
type Reasonings = Record<string, string>

const EVENT_OTHER = '__OTHER__'

export default function LabelPanel({ socket, state, messages, autoOpenTrigger }: Props) {
  const [open, setOpen] = useState(false)
  const [eventId, setEventId] = useState<string>(EVENT_OTHER)
  const [action, setAction] = useState<LabelAction>('other')
  const [actionArgs, setActionArgs] = useState('')
  const [targets, setTargets] = useState<Record<string, TargetUpdates>>({})
  const [reasonings, setReasonings] = useState<Reasonings>({})
  const [submitting, setSubmitting] = useState(false)
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [speechLanguage, setSpeechLanguage] = useState<'en' | 'de'>('en')
  const [isRecording, setIsRecording] = useState<Record<string, boolean>>({})
  const mediaRecorderRef = useRef<Record<string, MediaRecorder>>({})
  const wsRef = useRef<Record<string, WebSocket | null>>({})
  const currentInterimRef = useRef<Record<string, string>>({})
  const streamsRef = useRef<Record<string, MediaStream>>({})
  const audioChunksRef = useRef<Record<string, Blob[]>>({})
  const useFallbackRef = useRef<Record<string, boolean>>({})
  const silenceTimeoutRef = useRef<Record<string, any>>({})

  // Cleanup media recording, WebSockets, and audio streams on unmount
  useEffect(() => {
    return () => {
      Object.keys(mediaRecorderRef.current).forEach(playerId => {
        try {
          mediaRecorderRef.current[playerId]?.stop()
        } catch (e) {}
      })
      Object.keys(wsRef.current).forEach(playerId => {
        try {
          wsRef.current[playerId]?.close()
        } catch (e) {}
      })
      Object.keys(streamsRef.current).forEach(playerId => {
        try {
          streamsRef.current[playerId]?.getTracks().forEach(track => track.stop())
        } catch (e) {}
      })
      Object.keys(silenceTimeoutRef.current).forEach(playerId => {
        if (silenceTimeoutRef.current[playerId]) {
          clearTimeout(silenceTimeoutRef.current[playerId])
        }
      })
    }
  }, [])

  const me = state.players.find(p => p.id === state.myId)
  const isAlive = me?.isAlive ?? false
  const candidates = state.players.filter(p => p.isAlive && p.id !== state.myId)

  const systemEvents = useMemo(
    () => messages.filter(m => m.isSystem && DAY_LIKE_PHASES.has(m.phase)),
    [messages]
  )

  // Auto-open when a new daytime system event arrives.
  useEffect(() => {
    if (!autoOpenTrigger || !isAlive) return
    setEventId(autoOpenTrigger)
    setOpen(true)
  }, [autoOpenTrigger, isAlive])

  function resetForm() {
    setEventId(systemEvents.length > 0 ? systemEvents[systemEvents.length - 1].id : EVENT_OTHER)
    setAction('other')
    setActionArgs('')
    setTargets({})
    setReasonings({})
    setError(null)
    // Stop all active recordings, WebSockets, and streams
    Object.keys(mediaRecorderRef.current).forEach(playerId => {
      try {
        mediaRecorderRef.current[playerId]?.stop()
      } catch (e) {}
    })
    Object.keys(wsRef.current).forEach(playerId => {
      try {
        wsRef.current[playerId]?.close()
      } catch (e) {}
    })
    Object.keys(streamsRef.current).forEach(playerId => {
      try {
        streamsRef.current[playerId]?.getTracks().forEach(track => track.stop())
      } catch (e) {}
    })
    Object.keys(silenceTimeoutRef.current).forEach(playerId => {
      if (silenceTimeoutRef.current[playerId]) {
        clearTimeout(silenceTimeoutRef.current[playerId])
      }
    })
    silenceTimeoutRef.current = {}
    mediaRecorderRef.current = {}
    wsRef.current = {}
    streamsRef.current = {}
    currentInterimRef.current = {}
    setIsRecording({})
  }

  // After a successful submit, keep the event + action selected so the user
  // can quickly add a label for another player about the same event without
  // re-picking those fields. Only clear targets + reasonings.
  function clearForNextPlayer() {
    setTargets({})
    setReasonings({})
    setError(null)
    // Stop all active recordings, WebSockets, and streams
    Object.keys(mediaRecorderRef.current).forEach(playerId => {
      try {
        mediaRecorderRef.current[playerId]?.stop()
      } catch (e) {}
    })
    Object.keys(wsRef.current).forEach(playerId => {
      try {
        wsRef.current[playerId]?.close()
      } catch (e) {}
    })
    Object.keys(streamsRef.current).forEach(playerId => {
      try {
        streamsRef.current[playerId]?.getTracks().forEach(track => track.stop())
      } catch (e) {}
    })
    Object.keys(silenceTimeoutRef.current).forEach(playerId => {
      if (silenceTimeoutRef.current[playerId]) {
        clearTimeout(silenceTimeoutRef.current[playerId])
      }
    })
    silenceTimeoutRef.current = {}
    mediaRecorderRef.current = {}
    wsRef.current = {}
    streamsRef.current = {}
    currentInterimRef.current = {}
    setIsRecording({})
  }

  function toggleTarget(playerId: string) {
    setTargets(prev => {
      const next = { ...prev }
      if (next[playerId]) {
        delete next[playerId]
        // Stop media recording, close WebSocket, and stop stream if active when deselecting the target
        if (silenceTimeoutRef.current[playerId]) {
          clearTimeout(silenceTimeoutRef.current[playerId])
          delete silenceTimeoutRef.current[playerId]
        }
        if (mediaRecorderRef.current[playerId]) {
          try {
            mediaRecorderRef.current[playerId]?.stop()
          } catch (e) {}
        }
        if (wsRef.current[playerId]) {
          try {
            wsRef.current[playerId]?.close()
          } catch (e) {}
        }
        if (streamsRef.current[playerId]) {
          try {
            streamsRef.current[playerId]?.getTracks().forEach(track => track.stop())
            delete streamsRef.current[playerId]
          } catch (e) {}
        }
      } else {
        next[playerId] = {}
      }
      return next
    })
    // Drop any reasoning for a deselected target so it doesn't gate canSubmit.
    setReasonings(prev => {
      if (!prev[playerId]) return prev
      const next = { ...prev }
      delete next[playerId]
      if (currentInterimRef.current[playerId]) {
        delete currentInterimRef.current[playerId]
      }
      return next
    })
  }

  function setReasoningFor(playerId: string, value: string) {
    setReasonings(prev => ({ ...prev, [playerId]: value }))
  }

  async function startHttpRecording(playerId: string) {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      streamsRef.current[playerId] = stream

      let options = { mimeType: 'audio/webm' }
      let mediaRecorder: MediaRecorder
      try {
        mediaRecorder = new MediaRecorder(stream, options)
      } catch (e) {
        mediaRecorder = new MediaRecorder(stream)
      }

      audioChunksRef.current[playerId] = []

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current[playerId].push(event.data)
        }
      }

      mediaRecorder.onstop = () => {
        transcribeHttpAudio(playerId)
      }

      mediaRecorderRef.current[playerId] = mediaRecorder
      mediaRecorder.start()
      setIsRecording(prev => ({ ...prev, [playerId]: true }))
    } catch (err) {
      console.error(err)
      setError('Could not access microphone.')
    }
  }

  async function transcribeHttpAudio(playerId: string) {
    setIsRecording(prev => ({ ...prev, [playerId]: false }))
    
    // Stop tracks
    if (streamsRef.current[playerId]) {
      try {
        streamsRef.current[playerId].getTracks().forEach(track => track.stop())
        delete streamsRef.current[playerId]
      } catch (e) {}
    }

    if (!audioChunksRef.current[playerId] || audioChunksRef.current[playerId].length === 0) {
      return
    }

    const mediaRecorder = mediaRecorderRef.current[playerId]
    const audioBlob = new Blob(audioChunksRef.current[playerId], { type: mediaRecorder?.mimeType || 'audio/webm' })

    setReasonings(prev => ({ 
      ...prev, 
      [playerId]: (prev[playerId] ?? '') + (prev[playerId] ? ' ' : '') + '🎙️ [Transcribing...]' 
    }))

    try {
      const response = await fetch('/api/speech-to-text', {
        method: 'POST',
        headers: {
          'Content-Type': mediaRecorder?.mimeType || 'audio/webm',
          'X-Speech-Language': speechLanguage,
        },
        body: audioBlob,
      })

      const data = await response.json()

      setReasonings(prev => {
        const current = prev[playerId] ?? ''
        const cleanText = current.replace('🎙️ [Transcribing...]', '').trim()
        if (data.transcript) {
          return { ...prev, [playerId]: (cleanText + (cleanText ? ' ' : '') + data.transcript).trim() }
        }
        if (data.error) {
          setError(`Transcription error: ${data.error}`)
        }
        return { ...prev, [playerId]: cleanText }
      })
    } catch (err: any) {
      console.error(err)
      setError('Failed to contact speech-to-text service')
      setReasonings(prev => {
        const current = prev[playerId] ?? ''
        return { ...prev, [playerId]: current.replace('🎙️ [Transcribing...]', '').trim() }
      })
    }
  }

  function resetSilenceTimer(playerId: string) {
    if (silenceTimeoutRef.current[playerId]) {
      clearTimeout(silenceTimeoutRef.current[playerId])
    }
    silenceTimeoutRef.current[playerId] = setTimeout(() => {
      console.log(`Silence detected for ${playerId}, auto-stopping...`)
      stopRecording(playerId)
    }, 6000) // 6 seconds of silence
  }

  async function startRecording(playerId: string) {
    try {
      setError(null)
      currentInterimRef.current[playerId] = ''
      audioChunksRef.current[playerId] = []
      useFallbackRef.current[playerId] = false

      // 1. Fetch short-lived token from Next.js server
      let token = ''
      try {
        const tokenResponse = await fetch('/api/speech-token')
        const tokenData = await tokenResponse.json()
        token = tokenData.token
      } catch (e) {
        console.error('Failed to get token, falling back to HTTP', e)
        useFallbackRef.current[playerId] = true
      }

      if (useFallbackRef.current[playerId] || !token) {
        startHttpRecording(playerId)
        return
      }

      // 2. Establish direct real-time WebSocket connection to Deepgram
      const wsUrl = `wss://api.deepgram.com/v1/listen?model=nova-3&smart_format=true&interim_results=true&language=${speechLanguage}&numerals=true`
      const ws = new WebSocket(wsUrl, ['token', token])
      wsRef.current[playerId] = ws

      ws.onopen = async () => {
        resetSilenceTimer(playerId)
        try {
          const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
          streamsRef.current[playerId] = stream

          let options = { mimeType: 'audio/webm' }
          let mediaRecorder: MediaRecorder
          try {
            mediaRecorder = new MediaRecorder(stream, options)
          } catch (e) {
            // Fallback for Safari/iOS
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
          // Stream raw audio chunks every 100 milliseconds for low-latency feedback!
          mediaRecorder.start(100)
          setIsRecording(prev => ({ ...prev, [playerId]: true }))
        } catch (err: any) {
          console.error('Error starting MediaRecorder:', err)
          setError('Microphone access denied.')
          ws.close()
        }
      }

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          const transcript = data.channel?.alternatives?.[0]?.transcript || ''
          if (!transcript.trim()) return

          resetSilenceTimer(playerId)

          const isFinal = data.is_final

          setReasonings(prev => {
            const currentText = prev[playerId] ?? ''
            const oldInterim = currentInterimRef.current[playerId] || ''
            let baseText = currentText
            if (oldInterim && baseText.endsWith(oldInterim)) {
              baseText = baseText.substring(0, baseText.length - oldInterim.length).trim()
            }

            if (isFinal) {
              currentInterimRef.current[playerId] = ''
              const nextText = baseText + (baseText ? ' ' : '') + transcript.trim()
              return { ...prev, [playerId]: nextText }
            } else {
              const interimStr = ' ' + transcript.trim()
              currentInterimRef.current[playerId] = interimStr
              return { ...prev, [playerId]: baseText + interimStr }
            }
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
        if (silenceTimeoutRef.current[playerId]) {
          clearTimeout(silenceTimeoutRef.current[playerId])
          delete silenceTimeoutRef.current[playerId]
        }

        if (useFallbackRef.current[playerId]) {
          transcribeHttpAudio(playerId)
        } else {
          setIsRecording(prev => ({ ...prev, [playerId]: false }))
          
          // Remove any lingering interim text from the input when closing
          setReasonings(prev => {
            const currentText = prev[playerId] ?? ''
            const oldInterim = currentInterimRef.current[playerId] || ''
            if (oldInterim && currentText.endsWith(oldInterim)) {
              return { ...prev, [playerId]: currentText.substring(0, currentText.length - oldInterim.length).trim() }
            }
            return prev
          })
          currentInterimRef.current[playerId] = ''
          
          // Release tracks
          if (streamsRef.current[playerId]) {
            try {
              streamsRef.current[playerId].getTracks().forEach(track => track.stop())
              delete streamsRef.current[playerId]
            } catch (e) {}
          }
        }
      }

    } catch (err: any) {
      console.error(err)
      setError('Real-time connection failed. Falling back to HTTP...')
      startHttpRecording(playerId)
    }
  }

  function stopRecording(playerId: string) {
    if (silenceTimeoutRef.current[playerId]) {
      clearTimeout(silenceTimeoutRef.current[playerId])
      delete silenceTimeoutRef.current[playerId]
    }
    if (mediaRecorderRef.current[playerId]) {
      try {
        mediaRecorderRef.current[playerId]?.stop()
      } catch (e) {}
    }
    if (wsRef.current[playerId]) {
      try {
        wsRef.current[playerId]?.close()
      } catch (e) {}
    }
  }

  function toggleSpeechRecording(playerId: string) {
    if (isRecording[playerId]) {
      stopRecording(playerId)
    } else {
      startRecording(playerId)
    }
  }

  function setDimension(playerId: string, dim: TrustDimension, update: DimUpdate | null) {
    setTargets(prev => {
      const next = { ...prev }
      const cur: TargetUpdates = { ...(next[playerId] ?? {}) }
      if (update === null) delete cur[dim]
      else cur[dim] = update
      next[playerId] = cur
      return next
    })
  }

  const canSubmit = useMemo(() => {
    if (submitting) return false
    const targetIds = Object.keys(targets)
    if (targetIds.length === 0) return false
    for (const id of targetIds) {
      const t = targets[id]
      const updates = DIMENSIONS.filter(d => t[d.key])
      if (updates.length === 0) return false
      if (!(reasonings[id] ?? '').trim()) return false
    }
    return true
  }, [reasonings, targets, submitting])

  function requestBreak() {
    if (!state.labelingBreakAvailable) return
    socket.emit('label:request_break', (r) => {
      if (!r.success) setError(r.error ?? 'Could not start a break')
    })
  }

  function handleSubmit() {
    if (!canSubmit) return
    setSubmitting(true)
    setError(null)

    const targetIds = Object.keys(targets)
    const baseEvent = eventId === EVENT_OTHER ? null : eventId
    const baseArgs = actionArgs.trim() || null

    // One label per target, each carrying its own reasoning.
    const submits = targetIds.map(playerId => {
      const payload: LabelCreateInput = {
        eventId: baseEvent,
        action,
        actionArgs: baseArgs,
        reasoning: (reasonings[playerId] ?? '').trim(),
        targets: [{
          playerId,
          updates: DIMENSIONS
            .filter(d => targets[playerId][d.key])
            .map(d => ({ dimension: d.key, ...(targets[playerId][d.key] as DimUpdate) })),
        }],
      }
      return new Promise<{ playerId: string; ok: boolean; error?: string }>(resolve => {
        socket.emit('label:create', payload, r =>
          resolve({ playerId, ok: r.success, error: r.error })
        )
      })
    })

    Promise.all(submits).then(results => {
      setSubmitting(false)
      const failures = results.filter(r => !r.ok)
      if (failures.length === 0) {
        clearForNextPlayer()
        setSaved(true)
        setTimeout(() => setSaved(false), 2500)
        return
      }
      // Show which targets failed so the user knows what to retry.
      const failedNames = failures
        .map(f => state.players.find(p => p.id === f.playerId)?.name ?? '?')
        .join(', ')
      const firstErr = failures[0].error ?? 'Failed to save'
      setError(`${firstErr} (${failedNames})`)
    })
  }

  if (!isAlive) return null

  return (
    <div className="fixed bottom-4 left-4 z-40">
      {open ? (
        <div className="w-96 max-h-[80vh] bg-slate-900 border border-amber-800/60 rounded-xl shadow-xl flex flex-col">
          <div className="flex items-center justify-between px-3 py-2 border-b border-slate-700">
            <span className="text-xs font-semibold text-amber-300 uppercase tracking-wide">🏷️ Trust label</span>
            <div className="flex items-center gap-2">
              <button
                onClick={requestBreak}
                disabled={!state.labelingBreakAvailable}
                className="text-xs px-2 py-0.5 rounded border border-amber-800/60 text-amber-300 hover:bg-amber-950/40 disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer"
                title="Anonymously pause the phase deadline by 30 seconds so everyone has time to label"
              >
                ⏱ Ask for time
              </button>
              <button
                onClick={resetForm}
                className="text-xs text-slate-500 hover:text-amber-300 cursor-pointer"
                title="Clear all fields and start a fresh label"
              >
                + New
              </button>
              <button
                onClick={() => setOpen(false)}
                className="text-slate-500 hover:text-slate-300 text-sm leading-none cursor-pointer"
                aria-label="Close"
              >
                ✕
              </button>
            </div>
          </div>

          <div className="p-3 flex flex-col gap-3 overflow-y-auto">
            <div>
              <label className="text-xs text-slate-400 font-semibold">Event</label>
              <select
                value={eventId}
                onChange={e => setEventId(e.target.value)}
                className="w-full mt-1 bg-slate-800 border border-slate-700 rounded px-2 py-1.5 text-sm text-slate-100"
              >
                {systemEvents.map(m => (
                  <option key={m.id} value={m.id}>
                    R{m.round} · {truncate(m.content, 60)}
                  </option>
                ))}
                <option value={EVENT_OTHER}>🗣️ Other / general impression</option>
              </select>
            </div>

            <div>
              <label className="text-xs text-slate-400 font-semibold">Action</label>
              <select
                value={action}
                onChange={e => setAction(e.target.value as LabelAction)}
                className="w-full mt-1 bg-slate-800 border border-slate-700 rounded px-2 py-1.5 text-sm text-slate-100"
              >
                {LABEL_ACTIONS.map(a => (
                  <option key={a} value={a}>{ACTION_LABELS[a]}</option>
                ))}
              </select>
              <input
                value={actionArgs}
                onChange={e => setActionArgs(e.target.value)}
                placeholder="Optional: details (e.g. who, what)"
                maxLength={500}
                className="w-full mt-1.5 bg-slate-800 border border-slate-700 rounded px-2 py-1 text-xs text-slate-100 placeholder-slate-500"
              />
            </div>

            <div>
              <label className="text-xs text-slate-400 font-semibold">Affected players</label>
              <div className="mt-1 flex flex-wrap gap-1.5">
                {candidates.map(p => {
                  const selected = !!targets[p.id]
                  return (
                    <button
                      key={p.id}
                      onClick={() => toggleTarget(p.id)}
                      className={`px-2 py-1 rounded text-xs border transition-colors cursor-pointer ${
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
              return (
                <div key={playerId} className="border border-slate-700 rounded-lg p-2 bg-slate-800/40">
                  <div className="text-xs text-amber-200 font-semibold mb-2">{p.name}</div>
                  <div className="flex flex-col gap-2">
                    <div>
                      <div className="flex items-center justify-between mb-1">
                        <label className="text-[10px] uppercase tracking-wide text-slate-500 font-semibold">
                          Reasoning {isRecording[playerId] && <span className="text-red-400 normal-case animate-pulse ml-2">(Live recording...)</span>}
                        </label>
                        <div className="flex items-center gap-1.5">
                          <div className="flex bg-slate-900 border border-slate-800 rounded p-0.5 text-[9px] font-semibold text-slate-400">
                            <button
                              type="button"
                              onClick={() => setSpeechLanguage('en')}
                              disabled={isRecording[playerId]}
                              className={`px-1.5 py-0.5 rounded transition-all ${
                                speechLanguage === 'en'
                                  ? 'bg-amber-950/40 border border-amber-900/60 text-amber-200'
                                  : isRecording[playerId]
                                    ? 'opacity-30 cursor-not-allowed text-slate-600'
                                    : 'cursor-pointer hover:text-slate-200'
                              }`}
                            >
                              EN
                            </button>
                            <button
                              type="button"
                              onClick={() => setSpeechLanguage('de')}
                              disabled={isRecording[playerId]}
                              className={`px-1.5 py-0.5 rounded transition-all ${
                                speechLanguage === 'de'
                                  ? 'bg-amber-950/40 border border-amber-900/60 text-amber-200'
                                  : isRecording[playerId]
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
                              isRecording[playerId]
                                ? 'bg-red-950 border border-red-800 text-red-400 font-semibold animate-pulse scale-105'
                                : 'bg-slate-800 border border-slate-700 text-slate-300 hover:text-amber-300 hover:border-amber-700/60 hover:bg-slate-750'
                            }`}
                            title={isRecording[playerId] ? 'Stop voice recording' : `Speak reasoning in ${speechLanguage === 'en' ? 'English' : 'German'}`}
                          >
                            {isRecording[playerId] ? (
                              <>
                                <span className="w-2 h-2 rounded-full bg-red-500 animate-ping inline-block" />
                                <span>Stop/Mute</span>
                              </>
                            ) : (
                              <>
                                <span className="text-sm">🎙️</span>
                                <span>Voice Input</span>
                              </>
                            )}
                          </button>
                        </div>
                      </div>
                      <textarea
                        value={reasonings[playerId] ?? ''}
                        onChange={e => setReasoningFor(playerId, e.target.value)}
                        placeholder={`Why did your trust in ${p.name} change?`}
                        maxLength={2000}
                        rows={5}
                        className={`w-full mt-1 bg-slate-800 border rounded px-2 py-1.5 text-sm text-slate-100 placeholder-slate-500 resize-y min-h-[100px] focus:outline-none ${
                          isRecording[playerId]
                            ? 'border-red-500/80 shadow-[0_0_8px_rgba(239,68,68,0.2)] animate-pulse'
                            : 'border-slate-700 focus:border-amber-600'
                        }`}
                      />
                    </div>
                    {DIMENSIONS.map(d => {
                      const cur = targets[playerId][d.key]
                      const on = !!cur
                      return (
                        <div key={d.key} className="flex flex-col gap-1">
                          <button
                            onClick={() => setDimension(playerId, d.key, on ? null : { score: 4, confidence: 'medium' })}
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

            {saved && (
              <div className="text-xs text-emerald-300 bg-emerald-950/40 border border-emerald-800 rounded px-2 py-1 text-center">
                ✓ Saved — pick another player to label the same event, or click <span className="text-amber-300">+ New</span> to start over.
              </div>
            )}

            <button
              onClick={handleSubmit}
              disabled={!canSubmit}
              className="w-full py-2 bg-amber-700 hover:bg-amber-600 disabled:bg-slate-700 disabled:text-slate-500 text-amber-50 text-sm font-semibold rounded transition-colors cursor-pointer"
            >
              {submitting ? 'Saving…' : 'Save label'}
            </button>
          </div>
        </div>
      ) : (
        <button
          onClick={() => setOpen(true)}
          className="flex items-center gap-2 px-3 py-2 bg-slate-800 hover:bg-slate-700 border border-amber-800/60 rounded-xl shadow-lg text-sm text-amber-200 transition-colors cursor-pointer"
        >
          🏷️ <span>Label</span>
        </button>
      )}
    </div>
  )
}

function truncate(s: string, n: number): string {
  if (s.length <= n) return s
  return s.slice(0, n - 1) + '…'
}
