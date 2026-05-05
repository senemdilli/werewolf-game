'use client'

import { useState } from 'react'
import type { GameSocket } from '@/app/room/[code]/page'

interface SavedNote {
  content: string
  label: string
}

interface Props {
  socket: GameSocket
  phaseLabel: string
}

export default function NotePanel({ socket, phaseLabel }: Props) {
  const [open, setOpen] = useState(false)
  const [text, setText] = useState('')
  const [notes, setNotes] = useState<SavedNote[]>([])
  const [saved, setSaved] = useState(false)

  function handleSave() {
    const trimmed = text.trim()
    if (!trimmed) return
    socket.emit('note:save', trimmed)
    setNotes(prev => [{ content: trimmed, label: phaseLabel }, ...prev])
    setText('')
    setSaved(true)
    setTimeout(() => setSaved(false), 1500)
  }

  return (
    <div className="fixed bottom-4 right-4 z-40">
      {open ? (
        <div className="w-72 bg-slate-900 border border-slate-700 rounded-xl shadow-xl flex flex-col">
          <div className="flex items-center justify-between px-3 py-2 border-b border-slate-700">
            <span className="text-xs font-semibold text-slate-300 uppercase tracking-wide">📝 My Notes</span>
            <button
              onClick={() => setOpen(false)}
              className="text-slate-500 hover:text-slate-300 text-sm leading-none"
            >
              ✕
            </button>
          </div>

          <div className="p-3 flex flex-col gap-2">
            <textarea
              value={text}
              onChange={e => setText(e.target.value)}
              placeholder="What are you thinking? Who do you suspect?"
              maxLength={2000}
              rows={4}
              className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-100 placeholder-slate-500 resize-none focus:outline-none focus:border-violet-500"
            />
            <button
              onClick={handleSave}
              disabled={!text.trim()}
              className="w-full py-1.5 bg-violet-600 hover:bg-violet-700 disabled:bg-slate-700 disabled:text-slate-500 text-white text-sm rounded-lg transition-colors"
            >
              {saved ? '✓ Saved' : 'Save Note'}
            </button>
          </div>

          {notes.length > 0 && (
            <div className="border-t border-slate-700 px-3 py-2 max-h-48 overflow-y-auto space-y-2">
              {notes.map((n, i) => (
                <div key={i} className="text-xs">
                  <span className="text-slate-500">{n.label} — </span>
                  <span className="text-slate-300">{n.content}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      ) : (
        <button
          onClick={() => setOpen(true)}
          className="flex items-center gap-2 px-3 py-2 bg-slate-800 hover:bg-slate-700 border border-slate-600 rounded-xl shadow-lg text-sm text-slate-300 transition-colors"
        >
          📝 <span>Notes</span>
          {notes.length > 0 && (
            <span className="bg-violet-600 text-white text-xs rounded-full w-4 h-4 flex items-center justify-center">
              {notes.length}
            </span>
          )}
        </button>
      )}
    </div>
  )
}
