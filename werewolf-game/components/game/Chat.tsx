'use client'

import { useState, useEffect, useRef, useCallback } from 'react'
import type { ChatMessage } from '@/types/game'

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

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
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
                  {msg.playerName}
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

      <form onSubmit={handleSubmit} className="border-t border-slate-700 p-2 flex gap-2">
        <input
          value={input}
          onChange={e => setInput(e.target.value)}
          disabled={!canSend}
          placeholder={canSend ? (placeholder || 'Say something…') : 'You cannot chat right now'}
          maxLength={500}
          className="flex-1 bg-slate-800 border border-slate-700 rounded px-3 py-1.5 text-sm text-slate-100 placeholder-slate-500 disabled:opacity-50 focus:outline-none focus:border-violet-500"
        />
        <button
          type="submit"
          disabled={!canSend || !input.trim()}
          className="px-3 py-1.5 bg-violet-600 hover:bg-violet-700 disabled:bg-slate-700 disabled:text-slate-500 text-white text-sm rounded transition-colors"
        >
          Send
        </button>
      </form>
    </div>
  )
}
