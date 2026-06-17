'use client'

import { useState, useEffect, useRef, useCallback } from 'react'
import type { ChatMessage } from '@/types/game'
import PlayerName from './PlayerName'

interface Props {
  messages: ChatMessage[]
  onSend: (content: string) => void
  canSend: boolean
  placeholder?: string
}

const BOTTOM_THRESHOLD_PX = 40

export default function Chat({ messages, onSend, canSend, placeholder }: Props) {
  const [input, setInput] = useState('')
  const scrollRef = useRef<HTMLDivElement>(null)
  const bottomRef = useRef<HTMLDivElement>(null)
  const isAtBottomRef = useRef(true)
  const [unread, setUnread] = useState(0)

  // Speech-to-Text state and refs
  const [speechLanguage, setSpeechLanguage] = useState<'en' | 'de'>('en')
  const [isRecording, setIsRecording] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const wsRef = useRef<WebSocket | null>(null)
  const currentInterimRef = useRef('')
  const streamRef = useRef<MediaStream | null>(null)
  const audioChunksRef = useRef<Blob[]>([])
  const useFallbackRef = useRef(false)
  const silenceTimeoutRef = useRef<any>(null)

  const textareaRef = useRef<HTMLTextAreaElement>(null)

  // Auto-grow textarea height based on content
  useEffect(() => {
    const el = textareaRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, 120)}px`
  }, [input])

  // Auto-clear errors
  useEffect(() => {
    if (error) {
      const timer = setTimeout(() => setError(null), 4000)
      return () => clearTimeout(timer)
    }
  }, [error])

  // Stop recording function
  const stopRecording = useCallback(() => {
    if (silenceTimeoutRef.current) {
      clearTimeout(silenceTimeoutRef.current)
      silenceTimeoutRef.current = null
    }
    if (mediaRecorderRef.current) {
      try {
        mediaRecorderRef.current.stop()
      } catch (e) {}
      mediaRecorderRef.current = null
    }
    if (wsRef.current) {
      try {
        wsRef.current.close()
      } catch (e) {}
      wsRef.current = null
    }
    setIsRecording(false)
  }, [])

  // Auto-stop recording if permission to chat is lost (e.g. game phase transitions)
  useEffect(() => {
    if (!canSend && isRecording) {
      stopRecording()
    }
  }, [canSend, isRecording, stopRecording])

  // Cleanup
  useEffect(() => {
    return () => {
      if (silenceTimeoutRef.current) {
        clearTimeout(silenceTimeoutRef.current)
      }
      if (mediaRecorderRef.current) {
        try {
          mediaRecorderRef.current.stop()
        } catch (e) {}
      }
      if (wsRef.current) {
        try {
          wsRef.current.close()
        } catch (e) {}
      }
      if (streamRef.current) {
        try {
          streamRef.current.getTracks().forEach(track => track.stop())
        } catch (e) {}
      }
    }
  }, [])

  // Global stop-all-recordings listener (to coordinate with LabelPanel)
  useEffect(() => {
    const handleStopAll = () => {
      if (isRecording) {
        stopRecording()
      }
    }
    window.addEventListener('stop-all-recordings', handleStopAll)
    return () => {
      window.removeEventListener('stop-all-recordings', handleStopAll)
    }
  }, [isRecording, stopRecording])

  function resetSilenceTimer() {
    if (silenceTimeoutRef.current) {
      clearTimeout(silenceTimeoutRef.current)
    }
    silenceTimeoutRef.current = setTimeout(() => {
      console.log('Chat silence detected, auto-stopping...')
      stopRecording()
    }, 6000) // 6 seconds of silence
  }

  async function transcribeHttpAudio() {
    setIsRecording(false)
    
    if (streamRef.current) {
      try {
        streamRef.current.getTracks().forEach(track => track.stop())
        streamRef.current = null
      } catch (e) {}
    }

    if (audioChunksRef.current.length === 0) {
      return
    }

    const mediaRecorder = mediaRecorderRef.current
    const audioBlob = new Blob(audioChunksRef.current, { type: mediaRecorder?.mimeType || 'audio/webm' })

    setInput(prev => prev + (prev ? ' ' : '') + '🎙️ [Transcribing...]')

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

      setInput(prev => {
        const cleanText = prev.replace('🎙️ [Transcribing...]', '').trim()
        if (data.transcript) {
          return (cleanText + (cleanText ? ' ' : '') + data.transcript).trim()
        }
        if (data.error) {
          setError(`Transcription error: ${data.error}`)
        }
        return cleanText
      })
    } catch (err: any) {
      console.error(err)
      setError('Failed to contact speech-to-text service')
      setInput(prev => prev.replace('🎙️ [Transcribing...]', '').trim())
    }
  }

  async function startHttpRecording() {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      streamRef.current = stream

      let options = { mimeType: 'audio/webm' }
      let mediaRecorder: MediaRecorder
      try {
        mediaRecorder = new MediaRecorder(stream, options)
      } catch (e) {
        mediaRecorder = new MediaRecorder(stream)
      }

      audioChunksRef.current = []
      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data)
        }
      }

      mediaRecorder.onstop = () => {
        transcribeHttpAudio()
      }

      mediaRecorderRef.current = mediaRecorder
      mediaRecorder.start()
      setIsRecording(true)
    } catch (err) {
      console.error(err)
      setError('Could not access microphone.')
    }
  }

  async function startRecording() {
    try {
      setError(null)
      currentInterimRef.current = ''
      audioChunksRef.current = []
      useFallbackRef.current = false

      // Trigger global event to stop all other recordings (like in trust-labeling panel)
      window.dispatchEvent(new CustomEvent('stop-all-recordings'))

      // 1. Fetch short-lived token from Next.js server
      let token = ''
      try {
        const tokenResponse = await fetch('/api/speech-token')
        const tokenData = await tokenResponse.json()
        token = tokenData.token
      } catch (e) {
        console.error('Failed to get token, falling back to HTTP', e)
        useFallbackRef.current = true
      }

      if (useFallbackRef.current || !token) {
        startHttpRecording()
        return
      }

      // 2. Establish direct real-time WebSocket connection to Deepgram
      const wsUrl = `wss://api.deepgram.com/v1/listen?model=nova-3&smart_format=true&interim_results=true&language=${speechLanguage}&numerals=true`
      const ws = new WebSocket(wsUrl, ['token', token])
      wsRef.current = ws

      ws.onopen = async () => {
        resetSilenceTimer()
        try {
          const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
          streamRef.current = stream

          let options = { mimeType: 'audio/webm' }
          let mediaRecorder: MediaRecorder
          try {
            mediaRecorder = new MediaRecorder(stream, options)
          } catch (e) {
            mediaRecorder = new MediaRecorder(stream)
          }

          mediaRecorder.ondataavailable = (event) => {
            if (event.data.size > 0) {
              audioChunksRef.current.push(event.data)
              if (ws.readyState === WebSocket.OPEN && !useFallbackRef.current) {
                ws.send(event.data)
              }
            }
          }

          mediaRecorder.onstop = () => {
            if (ws.readyState === WebSocket.OPEN && !useFallbackRef.current) {
              ws.send(JSON.stringify({ type: 'CloseStream' }))
            }
          }

          mediaRecorderRef.current = mediaRecorder
          // Stream raw audio chunks every 100 milliseconds for low-latency feedback!
          mediaRecorder.start(100)
          setIsRecording(true)
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

          resetSilenceTimer()

          const isFinal = data.is_final

          setInput(prev => {
            const currentText = prev
            const oldInterim = currentInterimRef.current || ''
            let baseText = currentText
            if (oldInterim && baseText.endsWith(oldInterim)) {
              baseText = baseText.substring(0, baseText.length - oldInterim.length).trim()
            }

            if (isFinal) {
              currentInterimRef.current = ''
              return (baseText + (baseText ? ' ' : '') + transcript.trim()).trim()
            } else {
              const interimStr = ' ' + transcript.trim()
              currentInterimRef.current = interimStr
              return baseText + interimStr
            }
          })
        } catch (e) {
          console.error('Error parsing WebSocket message:', e)
        }
      }

      ws.onerror = (err) => {
        console.warn('WebSocket failed, using HTTP fallback...', err)
        useFallbackRef.current = true
      }

      ws.onclose = () => {
        if (silenceTimeoutRef.current) {
          clearTimeout(silenceTimeoutRef.current)
          silenceTimeoutRef.current = null
        }

        if (useFallbackRef.current) {
          transcribeHttpAudio()
        } else {
          setIsRecording(false)
          
          // Remove any lingering interim text from the input when closing
          setInput(prev => {
            const currentText = prev
            const oldInterim = currentInterimRef.current || ''
            if (oldInterim && currentText.endsWith(oldInterim)) {
              return currentText.substring(0, currentText.length - oldInterim.length).trim()
            }
            return prev
          })
          currentInterimRef.current = ''
          
          // Release tracks
          if (streamRef.current) {
            try {
              streamRef.current.getTracks().forEach(track => track.stop())
              streamRef.current = null
            } catch (e) {}
          }
        }
      }

    } catch (err: any) {
      console.error(err)
      setError('Real-time connection failed. Falling back to HTTP...')
      startHttpRecording()
    }
  }

  function toggleSpeechRecording() {
    if (isRecording) {
      stopRecording()
    } else {
      startRecording()
    }
  }

  const scrollToBottom = useCallback((behavior: ScrollBehavior = 'smooth') => {
    bottomRef.current?.scrollIntoView({ behavior, block: 'end' })
    isAtBottomRef.current = true
    setUnread(0)
  }, [])

  // On mount, jump to bottom without animation
  useEffect(() => {
    scrollToBottom('auto')
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // When messages arrive: scroll if user was at bottom, otherwise increment unread
  useEffect(() => {
    if (messages.length === 0) return
    if (isAtBottomRef.current) {
      scrollToBottom('smooth')
    } else {
      setUnread(c => c + 1)
    }
  }, [messages.length, scrollToBottom])

  function handleScroll() {
    const el = scrollRef.current
    if (!el) return
    const distanceFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight
    const wasAtBottom = isAtBottomRef.current
    const nowAtBottom = distanceFromBottom <= BOTTOM_THRESHOLD_PX
    isAtBottomRef.current = nowAtBottom
    if (nowAtBottom && !wasAtBottom) setUnread(0)
  }

  function handleSubmit(e: React.FormEvent | React.KeyboardEvent) {
    e.preventDefault()
    if (!canSend || isRecording) return
    const trimmed = input.trim()
    if (!trimmed) return
    onSend(trimmed)
    setInput('')
    // Sending a message means the user wants to see the conversation flow
    isAtBottomRef.current = true
    setUnread(0)
  }

  return (
    <div className="flex flex-col h-full relative">
      <div
        ref={scrollRef}
        onScroll={handleScroll}
        className="flex-1 overflow-y-auto space-y-1 p-3 min-h-0"
      >
        {messages.length === 0 && (
          <p className="text-slate-500 text-sm text-center mt-4">No messages yet</p>
        )}
        {messages.map(msg => (
          <div key={msg.id} className={`text-sm animate-fade-in ${msg.isSystem ? 'italic text-slate-400' : ''}`}>
            {msg.isSystem ? (
              <span>⚙ {msg.content}</span>
            ) : (
              <>
                <span className="font-semibold text-slate-300">
                  <PlayerName name={msg.playerName} showTeammateIcon={false} />
                </span>
                <span className="text-slate-500 text-xs ml-1">
                  [{msg.phase === 'night' ? 'night' : `day ${msg.round}`}]
                </span>
                <span className="text-slate-200 ml-1">{msg.content}</span>
              </>
            )}
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      {unread > 0 && (
        <button
          onClick={() => scrollToBottom('smooth')}
          className="absolute bottom-14 left-1/2 -translate-x-1/2 px-3 py-1 bg-violet-600 hover:bg-violet-700 text-white text-xs font-semibold rounded-full shadow-lg transition-colors flex items-center gap-1 z-10"
        >
          ↓ {unread} new message{unread === 1 ? '' : 's'}
        </button>
      )}

      {error && (
        <div className="absolute bottom-14 left-1/2 -translate-x-1/2 bg-red-950 border border-red-800 text-red-200 px-3 py-1.5 rounded text-xs rounded-lg shadow-lg z-20 animate-fade-in">
          ⚠️ {error}
        </div>
      )}

      <form onSubmit={handleSubmit} className="border-t border-slate-700 p-2 flex flex-col gap-1.5">
        <textarea
          ref={textareaRef}
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault()
              handleSubmit(e)
            }
          }}
          placeholder={placeholder || (canSend ? (isRecording ? 'Listening...' : 'Discuss with the village…') : 'You cannot send right now')}
          maxLength={500}
          disabled={isRecording}
          rows={1}
          className={`w-full bg-slate-800 border rounded px-3 py-2 text-sm text-slate-100 placeholder-slate-500 resize-none min-h-[38px] max-h-[120px] focus:outline-none transition-all duration-200 ${
            isRecording
              ? 'border-red-500/80 shadow-[0_0_8px_rgba(239,68,68,0.2)] animate-pulse font-medium text-red-100 placeholder-red-400/50'
              : 'border-slate-700 focus:border-violet-500'
          }`}
        />

        <div className="flex items-center justify-between gap-2 mt-0.5">
          <div>
            {canSend ? (
              <button
                type="button"
                onClick={toggleSpeechRecording}
                className={`flex items-center justify-center gap-1.5 px-2 py-1 rounded cursor-pointer transition-all duration-200 text-xs ${
                  isRecording
                    ? 'bg-red-950 border border-red-800 text-red-400 animate-pulse scale-105 shadow-[0_0_8px_rgba(239,68,68,0.2)] font-semibold'
                    : 'bg-slate-800 border border-slate-700 text-slate-350 hover:text-violet-300 hover:border-violet-600 hover:bg-slate-750'
                }`}
                title={isRecording ? 'Stop voice recording' : 'Speak in English (Only English allowed)'}
              >
                {isRecording ? (
                  <>
                    <span className="w-1.5 h-1.5 rounded-full bg-red-500 animate-ping inline-block" />
                    <span>REC</span>
                  </>
                ) : (
                  <>
                    <span className="text-[8px] font-bold text-slate-400 border border-slate-700 rounded px-1 py-0.25 bg-slate-900/50 select-none">EN</span>
                    <span className="text-xs">🎙️</span>
                    <span className="text-[10px] text-slate-400 font-medium">Voice Input</span>
                  </>
                )}
              </button>
            ) : (
              <div />
            )}
          </div>

          <button
            type="submit"
            disabled={!canSend || !input.trim() || isRecording}
            title={!canSend ? 'You cannot send right now' : undefined}
            className="px-3.5 py-1.5 bg-violet-600 hover:bg-violet-750 disabled:bg-slate-700 disabled:text-slate-500 disabled:cursor-not-allowed text-white text-xs font-bold rounded transition-colors flex items-center justify-center"
          >
            Send
          </button>
        </div>
      </form>
    </div>
  )
}
