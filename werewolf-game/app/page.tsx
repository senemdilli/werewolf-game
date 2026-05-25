'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { connectSocket } from '@/lib/socket-client'
import type { GameMode, WitchSelfHealSetting } from '@/types/game'

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
  const [gameMode, setGameMode] = useState<GameMode>('classic')
  const [witchSelfHeal, setWitchSelfHeal] = useState<WitchSelfHealSetting>('first_round')
  const [speakDuration, setSpeakDuration] = useState<number>(60)
  const [bidDuration, setBidDuration] = useState<number>(60)
  const [showSettings, setShowSettings] = useState(false)
  const [name, setName] = useState('')
  const [code, setCode] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    sessionStorage.removeItem('ww_playerId')
    sessionStorage.removeItem('ww_roomCode')
    // Surface a message that survived a redirect (e.g. host kicked us).
    const lastError = sessionStorage.getItem('ww_lastError')
    if (lastError) {
      setError(lastError)
      sessionStorage.removeItem('ww_lastError')
    }
  }, [])

  function handleCreate() {
    if (!name.trim()) return setError('Enter your name')
    setLoading(true)
    setError('')

    const socket = connectSocket()
    socket.emit(
      'room:create',
      {
        playerName: name.trim(),
        gameMode,
        witchSelfHeal,
        ...(gameMode === 'arena' ? { speakDuration, bidDuration } : {}),
      },
      ({ roomCode, playerId }) => {
        sessionStorage.setItem('ww_playerId', playerId)
        sessionStorage.setItem('ww_roomCode', roomCode)
        router.push(`/room/${roomCode}`)
      }
    )
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
              href="/how-to-play"
              className="block text-center text-slate-500 hover:text-slate-300 text-sm mt-4 transition-colors"
            >
              How to play? →
            </a>
            <a
              href="/admin"
              className="block text-center text-slate-500 hover:text-slate-300 text-sm transition-colors"
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

            <div>
              <p className="text-xs uppercase tracking-wide text-slate-400 font-semibold mb-2">Game mode</p>
              <div className="grid grid-cols-2 gap-2">
                <button
                  type="button"
                  onClick={() => setGameMode('classic')}
                  className={`text-left rounded-lg border px-3 py-2 transition-colors cursor-pointer ${
                    gameMode === 'classic'
                      ? 'border-violet-500 bg-violet-950/40 text-violet-200'
                      : 'border-slate-700 bg-slate-800/40 text-slate-300 hover:border-slate-500'
                  }`}
                >
                  <p className="text-sm font-semibold">Classic</p>
                  <p className="text-xs text-slate-400 mt-0.5">Free-form chat, group day-vote, double-weight Mayor.</p>
                </button>
                <button
                  type="button"
                  onClick={() => setGameMode('arena')}
                  className={`text-left rounded-lg border px-3 py-2 transition-colors cursor-pointer ${
                    gameMode === 'arena'
                      ? 'border-amber-500 bg-amber-950/40 text-amber-200'
                      : 'border-slate-700 bg-slate-800/40 text-slate-300 hover:border-slate-500'
                  }`}
                >
                  <p className="text-sm font-semibold">Arena</p>
                  <p className="text-xs text-slate-400 mt-0.5">Structured rounds, bidding to speak, Mayor breaks ties.</p>
                </button>
              </div>
              <a href="/how-to-play" className="block text-xs text-slate-500 hover:text-slate-300 mt-2 transition-colors">Compare rules →</a>
            </div>

            {/* Collapsible Game Settings */}
            <div className="border-t border-slate-800/80 pt-4">
              <button
                type="button"
                onClick={() => setShowSettings(!showSettings)}
                className="w-full flex items-center justify-between text-xs font-semibold uppercase tracking-wider text-slate-400 hover:text-slate-200 transition-colors cursor-pointer"
              >
                <span>⚙️ Game Settings</span>
                <span className="text-slate-500 font-mono text-sm">
                  {showSettings ? '▲' : '▼'}
                </span>
              </button>

              {showSettings && (
                <div className="mt-4 space-y-4 animate-fadeIn">
                  <div>
                    <p className="text-xs font-semibold text-slate-400 mb-2">Witch Self-Healing</p>
                    <div className="grid grid-cols-3 gap-2">
                      <button
                        type="button"
                        onClick={() => setWitchSelfHeal('always')}
                        className={`text-left rounded-lg border px-3 py-2 transition-colors cursor-pointer flex flex-col justify-between h-22 ${
                          witchSelfHeal === 'always'
                            ? 'border-violet-500 bg-violet-950/40 text-violet-200'
                            : 'border-slate-700 bg-slate-800/40 text-slate-300 hover:border-slate-500'
                        }`}
                      >
                        <p className="text-xs font-semibold">Always</p>
                        <p className="text-[10px] text-slate-400 mt-1 leading-tight">Can self-heal in any round.</p>
                      </button>
                      <button
                        type="button"
                        onClick={() => setWitchSelfHeal('first_round')}
                        className={`text-left rounded-lg border px-3 py-2 transition-colors cursor-pointer flex flex-col justify-between h-22 ${
                          witchSelfHeal === 'first_round'
                            ? 'border-violet-500 bg-violet-950/40 text-violet-200'
                            : 'border-slate-700 bg-slate-800/40 text-slate-300 hover:border-slate-500'
                        }`}
                      >
                        <p className="text-xs font-semibold">Round 1 Only</p>
                        <p className="text-[10px] text-slate-400 mt-1 leading-tight">Can only self-heal in Night 1.</p>
                      </button>
                      <button
                        type="button"
                        onClick={() => setWitchSelfHeal('never')}
                        className={`text-left rounded-lg border px-3 py-2 transition-colors cursor-pointer flex flex-col justify-between h-22 ${
                          witchSelfHeal === 'never'
                            ? 'border-violet-500 bg-violet-950/40 text-violet-200'
                            : 'border-slate-700 bg-slate-800/40 text-slate-300 hover:border-slate-500'
                        }`}
                      >
                        <p className="text-xs font-semibold">Never</p>
                        <p className="text-[10px] text-slate-400 mt-1 leading-tight">Can never self-heal.</p>
                      </button>
                    </div>
                  </div>

                  {gameMode === 'arena' && (
                    <>
                      {/* Bidding Time (Arena) */}
                      <div>
                        <div className="flex items-center gap-1.5 mb-2">
                          <p className="text-xs font-semibold text-slate-400">Bidding Duration</p>
                          <span className="text-[9px] px-1 bg-amber-950/40 text-amber-400 border border-amber-800/40 rounded uppercase font-bold">Arena Only</span>
                        </div>
                        <div className="grid grid-cols-3 gap-2">
                          {[30, 60, 90].map((t) => (
                            <button
                              key={t}
                              type="button"
                              onClick={() => setBidDuration(t)}
                              className={`text-center rounded-lg border py-1.5 transition-colors cursor-pointer text-xs font-semibold ${
                                bidDuration === t
                                  ? 'border-violet-500 bg-violet-950/40 text-violet-200'
                                  : 'border-slate-700 bg-slate-800/40 text-slate-300 hover:border-slate-500'
                              }`}
                            >
                              {t}s {t === 60 && <span className="opacity-60 text-[10px]">(Default)</span>}
                            </button>
                          ))}
                        </div>
                      </div>

                      {/* Speaking Time (Arena) */}
                      <div>
                        <div className="flex items-center gap-1.5 mb-2">
                          <p className="text-xs font-semibold text-slate-400">Speaking Duration</p>
                          <span className="text-[9px] px-1 bg-amber-950/40 text-amber-400 border border-amber-800/40 rounded uppercase font-bold">Arena Only</span>
                        </div>
                        <div className="grid grid-cols-3 gap-2">
                          {[30, 60, 90].map((t) => (
                            <button
                              key={t}
                              type="button"
                              onClick={() => setSpeakDuration(t)}
                              className={`text-center rounded-lg border py-1.5 transition-colors cursor-pointer text-xs font-semibold ${
                                speakDuration === t
                                  ? 'border-violet-500 bg-violet-950/40 text-violet-200'
                                  : 'border-slate-700 bg-slate-800/40 text-slate-300 hover:border-slate-500'
                              }`}
                            >
                              {t}s {t === 60 && <span className="opacity-60 text-[10px]">(Default)</span>}
                            </button>
                          ))}
                        </div>
                      </div>
                    </>
                  )}
                </div>
              )}
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
