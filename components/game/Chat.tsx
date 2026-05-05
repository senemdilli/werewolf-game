'use client'

import { useState, useEffect, useRef } from 'react'
import type { ChatMessage, Role } from '@/types/game'

const roleColor: Record<Role, string> = {
  werewolf: 'text-red-400',
  villager: 'text-blue-400',
  seer:     'text-amber-400',
  doctor:   'text-emerald-400',
  mayor:    'text-violet-400',
}

interface Props {
  messages: ChatMessage[]
  onSend: (content: string) => void
  canSend: boolean
  placeholder?: string
}

export default function Chat({ messages, onSend, canSend, placeholder }: Props) {
  const [input, setInput] = useState('')
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    const trimmed = input.trim()
    if (!trimmed) return
    onSend(trimmed)
    setInput('')
  }

  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 overflow-y-auto space-y-1 p-3 min-h-0">
        {messages.length === 0 && (
          <p className="text-slate-500 text-sm text-center mt-4">No messages yet</p>
        )}
        {messages.map(msg => (
          <div key={msg.id} className={`text-sm animate-fade-in ${msg.isSystem ? 'italic text-slate-400' : ''}`}>
            {msg.isSystem ? (
              <span>⚙ {msg.content}</span>
            ) : (
              <>
                <span className={`font-semibold ${msg.role ? roleColor[msg.role] : 'text-slate-300'}`}>
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
