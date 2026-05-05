'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { connectSocket } from '@/lib/socket-client'

const RANDOM_NAMES = [
  'Aldric', 'Beatrix', 'Casimir', 'Delara', 'Edmund',
  'Fiona', 'Garrett', 'Helena', 'Isidore', 'Juliana',
  'Kieran', 'Lyra', 'Magnus', 'Nadia', 'Oswin',
  'Petra', 'Rowena', 'Stellan', 'Tamsin', 'Ulric',
  'Vesper', 'Wren', 'Xander', 'Yara', 'Zephyr',
  'Alaric', 'Briar', 'Corvus', 'Dusk', 'Ember',
]

type Mode = 'home' | 'create' | 'join'

export default function Home() {
  const router = useRouter()
  const [mode, setMode] = useState<Mode>('home')
  const [name, setName] = useState('')
  const [code, setCode] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    sessionStorage.removeItem('ww_playerId')
    sessionStorage.removeItem('ww_roomCode')
  }, [])

  function handleCreate() {
    if (!name.trim()) return setError('Enter your name')
    setLoading(true)
    setError('')

    const socket = connectSocket()
    socket.emit('room:create', name.trim(), ({ roomCode, playerId }) => {
      sessionStorage.setItem('ww_playerId', playerId)
      sessionStorage.setItem('ww_roomCode', roomCode)
      router.push(`/room/${roomCode}`)
    })
  }

  function handleJoin() {
    if (!name.trim()) return setError('Enter your name')
    if (!code.trim()) return setError('Enter a room code')
    setLoading(true)
    setError('')

    const socket = connectSocket()
    socket.emit('room:join', { roomCode: code.trim().toUpperCase(), playerName: name.trim() }, (res) => {
      if (!res.success) {
        setError(res.error || 'Failed to join')
        setLoading(false)
        return
      }
      sessionStorage.setItem('ww_playerId', res.playerId!)
      sessionStorage.setItem('ww_roomCode', code.trim().toUpperCase())
      router.push(`/room/${code.trim().toUpperCase()}`)
    })
  }

  return (
    <div className="min-h-screen flex flex-col items-center justify-center px-4">
      <div className="w-full max-w-sm">
        <div className="text-center mb-10">
          <div className="text-7xl mb-4">🐺</div>
          <h1 className="text-4xl font-black text-slate-100">Werewolf</h1>
          <p className="text-slate-400 mt-2 text-sm">A social deduction game</p>
        </div>

        {mode === 'home' && (
          <div className="space-y-3">
            <button
              onClick={() => setMode('create')}
              className="w-full py-3 bg-violet-600 hover:bg-violet-700 text-white font-semibold rounded-xl transition-colors cursor-pointer"
            >
              Create a game
            </button>
            <button
              onClick={() => setMode('join')}
              className="w-full py-3 bg-slate-800 hover:bg-slate-700 text-slate-200 font-semibold rounded-xl transition-colors border border-slate-700 cursor-pointer"
            >
              Join a game
            </button>
            <a
              href="/admin"
              className="block text-center text-slate-500 hover:text-slate-300 text-sm mt-4 transition-colors"
            >
              Research admin →
            </a>
          </div>
        )}

        {mode === 'create' && (
          <div className="bg-slate-900 border border-slate-700 rounded-2xl p-6 space-y-4">
            <h2 className="font-semibold text-lg">Create game</h2>
            <div className="flex gap-2">
              <input
                autoFocus
                value={name}
                onChange={e => setName(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && handleCreate()}
                placeholder="Your name"
                maxLength={20}
                className="flex-1 bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-violet-500 placeholder-slate-500"
              />
              <button
                onClick={() => setName(RANDOM_NAMES[Math.floor(Math.random() * RANDOM_NAMES.length)])}
                className="px-3 py-2 bg-slate-700 hover:bg-slate-600 rounded-lg text-sm text-slate-300 transition-colors cursor-pointer shrink-0"
                title="Random name"
              >🎲</button>
            </div>
            {error && <p className="text-red-400 text-sm">{error}</p>}
            <button
              disabled={loading}
              onClick={handleCreate}
              className="w-full py-2.5 bg-violet-600 hover:bg-violet-700 disabled:opacity-50 text-white font-semibold rounded-lg transition-colors cursor-pointer"
            >
              {loading ? 'Creating…' : 'Create room'}
            </button>
            <button onClick={() => { setMode('home'); setError('') }} className="w-full text-slate-500 hover:text-slate-300 text-sm transition-colors cursor-pointer">
              ← Back
            </button>
          </div>
        )}

        {mode === 'join' && (
          <div className="bg-slate-900 border border-slate-700 rounded-2xl p-6 space-y-4">
            <h2 className="font-semibold text-lg">Join game</h2>
            <div className="flex gap-2">
              <input
                autoFocus
                value={name}
                onChange={e => setName(e.target.value)}
                placeholder="Your name"
                maxLength={20}
                className="flex-1 bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-violet-500 placeholder-slate-500"
              />
              <button
                onClick={() => setName(RANDOM_NAMES[Math.floor(Math.random() * RANDOM_NAMES.length)])}
                className="px-3 py-2 bg-slate-700 hover:bg-slate-600 rounded-lg text-sm text-slate-300 transition-colors cursor-pointer shrink-0"
                title="Random name"
              >🎲</button>
            </div>
            <input
              value={code}
              onChange={e => setCode(e.target.value.toUpperCase())}
              onKeyDown={e => e.key === 'Enter' && handleJoin()}
              placeholder="Room code (e.g. ABC123)"
              maxLength={6}
              className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:border-violet-500 placeholder-slate-500 uppercase"
            />
            {error && <p className="text-red-400 text-sm">{error}</p>}
            <button
              disabled={loading}
              onClick={handleJoin}
              className="w-full py-2.5 bg-violet-600 hover:bg-violet-700 disabled:opacity-50 text-white font-semibold rounded-lg transition-colors cursor-pointer"
            >
              {loading ? 'Joining…' : 'Join room'}
            </button>
            <button onClick={() => { setMode('home'); setError('') }} className="w-full text-slate-500 hover:text-slate-300 text-sm transition-colors cursor-pointer">
              ← Back
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
