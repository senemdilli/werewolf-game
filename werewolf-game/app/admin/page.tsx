'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'

interface GameSummary {
  id: string
  roomCode: string
  gameMode: 'CLASSIC' | 'ARENA'
  status: string
  winner: string | null
  playerCount: number
  totalRounds: number
  startedAt: string | null
  endedAt: string | null
  createdAt: string
  isSandbox: boolean
  isArchived: boolean
  _count: { messages: number; players: number }
}

type FilterType = 'all' | 'normal' | 'sandbox' | 'archived'

export default function AdminPage() {
  const router = useRouter()
  const [games, setGames] = useState<GameSummary[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [pages, setPages] = useState(1)
  const [filter, setFilter] = useState<FilterType>('all')
  const [loading, setLoading] = useState(true)

  async function handleLogout() {
    await fetch('/api/admin/auth', { method: 'DELETE' })
    router.push('/admin/login')
  }

  const fetchGames = () => {
    setLoading(true)
    const isArchived = filter === 'archived'
    fetch(`/api/admin/games?page=${page}&type=${filter}&archived=${isArchived}`)
      .then(r => r.json())
      .then(data => {
        setGames(data.games)
        setTotal(data.total)
        setPages(data.pages)
      })
      .catch(err => console.error('Failed to fetch games:', err))
      .finally(() => setLoading(false))
  }

  // Reset page when filter changes
  useEffect(() => {
    setPage(1)
  }, [filter])

  // Fetch games on page or filter changes
  useEffect(() => {
    fetchGames()
  }, [page, filter])

  function exportCsv(gameId: string) {
    window.open(`/api/admin/export/${gameId}`, '_blank')
  }

  function exportLabelsJson(gameId: string) {
    window.open(`/api/admin/export/${gameId}/labels`, '_blank')
  }

  async function handleStopGame(gameId: string) {
    if (!window.confirm('Are you sure you want to stop and terminate this active game? All players will be kicked.')) return
    try {
      const res = await fetch(`/api/admin/games/${gameId}`, { method: 'POST' })
      if (!res.ok) throw new Error('Failed to stop game')
      fetchGames()
    } catch (err) {
      alert('Error: ' + (err as any).message)
    }
  }

  async function handleToggleArchive(gameId: string, archive: boolean) {
    const action = archive ? 'archive' : 'restore'
    if (!window.confirm(`Are you sure you want to ${action} this game?`)) return
    try {
      const res = await fetch(`/api/admin/games/${gameId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ isArchived: archive }),
      })
      if (!res.ok) throw new Error(`Failed to ${action} game`)
      fetchGames()
    } catch (err) {
      alert('Error: ' + (err as any).message)
    }
  }

  const winnerBadge = (w: string | null) => {
    if (!w) return <span className="text-slate-500 text-xs">-</span>
    return (
      <span className={`text-xs px-2 py-0.5 rounded border ${
        w === 'VILLAGERS'
          ? 'text-blue-400 bg-blue-950/50 border-blue-800'
          : 'text-red-400 bg-red-950/50 border-red-800'
      }`}>
        {w.toLowerCase()}
      </span>
    )
  }

  const statusBadge = (s: string) => {
    if (s === 'FINISHED') {
      return (
        <span className="text-xs px-2 py-0.5 rounded border text-emerald-400 bg-emerald-950/50 border-emerald-800">
          finished
        </span>
      )
    }
    if (s === 'IN_PROGRESS') {
      return (
        <span className="text-xs px-2 py-0.5 rounded border text-amber-400 bg-amber-950/50 border-amber-800">
          in progress
        </span>
      )
    }
    if (s === 'CANCELED') {
      return (
        <span className="text-xs px-2 py-0.5 rounded border text-slate-400 bg-slate-950/50 border-slate-700">
          canceled
        </span>
      )
    }
    return (
      <span className="text-xs px-2 py-0.5 rounded border text-slate-400 border-slate-700">
        {s.toLowerCase().replace('_', ' ')}
      </span>
    )
  }

  return (
    <div className="min-h-screen p-6 max-w-6xl mx-auto">
      <div className="mb-8 flex items-start justify-between">
        <div>
          <a href="/" className="text-slate-500 hover:text-slate-300 text-sm">← Back to game</a>
          <h1 className="text-2xl font-bold text-slate-100 mt-2">Research Admin</h1>
          <p className="text-slate-400 text-sm mt-1">{total} games found</p>
        </div>
        <button
          onClick={handleLogout}
          className="text-xs px-3 py-1.5 bg-slate-800 hover:bg-slate-700 border border-slate-600 rounded transition-colors cursor-pointer text-slate-300"
        >
          Logout
        </button>
      </div>

      {/* Tabs */}
      <div className="mb-6 flex border-b border-slate-800">
        {(['all', 'normal', 'sandbox', 'archived'] as const).map(t => (
          <button
            key={t}
            onClick={() => setFilter(t)}
            className={`px-4 py-2 text-sm font-semibold border-b-2 capitalize transition-colors cursor-pointer ${
              filter === t
                ? 'border-violet-500 text-violet-400'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            {t === 'all' ? 'All Games' : t === 'normal' ? 'Normal Games' : t === 'sandbox' ? 'Sandbox Games' : 'Archived Games'}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="text-slate-400 animate-pulse">Loading games…</div>
      ) : games.length === 0 ? (
        <div className="text-slate-500 text-center py-20">No games recorded yet</div>
      ) : (
        <>
          <div className="overflow-x-auto rounded-xl border border-slate-700">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-700 bg-slate-900">
                  <th className="text-left px-4 py-3 text-slate-400 font-medium">Room</th>
                  <th className="text-left px-4 py-3 text-slate-400 font-medium">Mode</th>
                  <th className="text-left px-4 py-3 text-slate-400 font-medium">Status</th>
                  <th className="text-left px-4 py-3 text-slate-400 font-medium">Winner</th>
                  <th className="text-left px-4 py-3 text-slate-400 font-medium">Players</th>
                  <th className="text-left px-4 py-3 text-slate-400 font-medium">Rounds</th>
                  <th className="text-left px-4 py-3 text-slate-400 font-medium">Messages</th>
                  <th className="text-left px-4 py-3 text-slate-400 font-medium">Started</th>
                  <th className="text-left px-4 py-3 text-slate-400 font-medium">Actions</th>
                </tr>
              </thead>
              <tbody>
                {games.map((g, i) => (
                  <tr key={g.id} className={`border-b border-slate-800 ${i % 2 === 0 ? 'bg-slate-900/30' : ''}`}>
                    <td className="px-4 py-3 font-mono text-violet-400 font-bold">{g.roomCode}</td>
                    <td className="px-4 py-3">
                      <div className="flex flex-col gap-1 items-start">
                        <span className={`text-xs px-2 py-0.5 rounded border ${
                          g.gameMode === 'ARENA'
                            ? 'text-amber-300 bg-amber-950/50 border-amber-800'
                            : 'text-violet-300 bg-violet-950/50 border-violet-800'
                        }`}>
                          {g.gameMode.toLowerCase()}
                        </span>
                        {g.isSandbox && (
                          <span className="text-[9px] px-1 bg-amber-950/40 text-amber-400 border border-amber-800/40 rounded uppercase font-bold select-none">
                            🧪 sandbox
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="px-4 py-3">{statusBadge(g.status)}</td>
                    <td className="px-4 py-3">{winnerBadge(g.winner)}</td>
                    <td className="px-4 py-3 text-slate-300">{g._count.players}</td>
                    <td className="px-4 py-3 text-slate-300">{g.totalRounds}</td>
                    <td className="px-4 py-3 text-slate-300">{g._count.messages}</td>
                    <td className="px-4 py-3 text-slate-400 text-xs">
                      {g.startedAt ? new Date(g.startedAt).toLocaleString() : '—'}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-1.5 flex-wrap">
                        {/* Exports for non-active/finished games */}
                        {g.status === 'FINISHED' && (
                          <>
                            <button
                              onClick={() => exportCsv(g.id)}
                              className="text-xs px-2 py-1 bg-slate-800 hover:bg-slate-700 border border-slate-600 rounded transition-colors cursor-pointer"
                            >
                              CSV
                            </button>
                            <button
                              onClick={() => exportLabelsJson(g.id)}
                              className="text-xs px-2 py-1 bg-slate-800 hover:bg-slate-700 border border-amber-800/60 text-amber-200 rounded transition-colors cursor-pointer"
                              title="Trust-label survey data"
                            >
                              JSON
                            </button>
                          </>
                        )}

                        {/* Stop active games */}
                        {g.status === 'IN_PROGRESS' && (
                          <button
                            onClick={() => handleStopGame(g.id)}
                            className="text-xs px-2.5 py-1 bg-red-950/40 hover:bg-red-900/40 border border-red-800/60 text-red-200 rounded transition-colors cursor-pointer font-medium"
                          >
                            Stop
                          </button>
                        )}

                        {/* Archive / Restore actions */}
                        {!g.isArchived ? (
                          <button
                            onClick={() => handleToggleArchive(g.id, true)}
                            className="text-xs px-2.5 py-1 bg-slate-900 hover:bg-slate-800 border border-slate-700 text-slate-400 hover:text-slate-300 rounded transition-colors cursor-pointer"
                          >
                            Archive
                          </button>
                        ) : (
                          <button
                            onClick={() => handleToggleArchive(g.id, false)}
                            className="text-xs px-2.5 py-1 bg-violet-950/40 hover:bg-violet-900/40 border border-violet-800/60 text-violet-200 rounded transition-colors cursor-pointer font-medium"
                          >
                            Restore
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {pages > 1 && (
            <div className="flex items-center justify-center gap-3 mt-6">
              <button
                disabled={page === 1}
                onClick={() => setPage(p => p - 1)}
                className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 disabled:opacity-40 rounded text-sm cursor-pointer"
              >
                ← Prev
              </button>
              <span className="text-slate-400 text-sm">Page {page} of {pages}</span>
              <button
                disabled={page === pages}
                onClick={() => setPage(p => p + 1)}
                className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 disabled:opacity-40 rounded text-sm cursor-pointer"
              >
                Next →
              </button>
            </div>
          )}
        </>
      )}
    </div>
  )
}
