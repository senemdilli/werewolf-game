'use client'

import { useEffect, useState } from 'react'

interface GameSummary {
  id: string
  roomCode: string
  status: string
  winner: string | null
  playerCount: number
  totalRounds: number
  startedAt: string | null
  endedAt: string | null
  createdAt: string
  _count: { messages: number; players: number }
}

export default function AdminPage() {
  const [games, setGames] = useState<GameSummary[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [pages, setPages] = useState(1)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    fetch(`/api/admin/games?page=${page}`)
      .then(r => r.json())
      .then(data => {
        setGames(data.games)
        setTotal(data.total)
        setPages(data.pages)
      })
      .finally(() => setLoading(false))
  }, [page])

  function exportCsv(gameId: string) {
    window.open(`/api/admin/export/${gameId}`, '_blank')
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

  return (
    <div className="min-h-screen p-6 max-w-6xl mx-auto">
      <div className="mb-8">
        <a href="/" className="text-slate-500 hover:text-slate-300 text-sm">← Back to game</a>
        <h1 className="text-2xl font-bold text-slate-100 mt-2">Research Admin</h1>
        <p className="text-slate-400 text-sm mt-1">{total} total games recorded</p>
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
                  <th className="text-left px-4 py-3 text-slate-400 font-medium">Status</th>
                  <th className="text-left px-4 py-3 text-slate-400 font-medium">Winner</th>
                  <th className="text-left px-4 py-3 text-slate-400 font-medium">Players</th>
                  <th className="text-left px-4 py-3 text-slate-400 font-medium">Rounds</th>
                  <th className="text-left px-4 py-3 text-slate-400 font-medium">Messages</th>
                  <th className="text-left px-4 py-3 text-slate-400 font-medium">Started</th>
                  <th className="text-left px-4 py-3 text-slate-400 font-medium">Export</th>
                </tr>
              </thead>
              <tbody>
                {games.map((g, i) => (
                  <tr key={g.id} className={`border-b border-slate-800 ${i % 2 === 0 ? 'bg-slate-900/30' : ''}`}>
                    <td className="px-4 py-3 font-mono text-violet-400 font-bold">{g.roomCode}</td>
                    <td className="px-4 py-3">
                      <span className={`text-xs px-2 py-0.5 rounded border ${
                        g.status === 'FINISHED'
                          ? 'text-emerald-400 bg-emerald-950/50 border-emerald-800'
                          : g.status === 'IN_PROGRESS'
                          ? 'text-amber-400 bg-amber-950/50 border-amber-800'
                          : 'text-slate-400 border-slate-700'
                      }`}>
                        {g.status.toLowerCase().replace('_', ' ')}
                      </span>
                    </td>
                    <td className="px-4 py-3">{winnerBadge(g.winner)}</td>
                    <td className="px-4 py-3 text-slate-300">{g._count.players}</td>
                    <td className="px-4 py-3 text-slate-300">{g.totalRounds}</td>
                    <td className="px-4 py-3 text-slate-300">{g._count.messages}</td>
                    <td className="px-4 py-3 text-slate-400 text-xs">
                      {g.startedAt ? new Date(g.startedAt).toLocaleString() : '—'}
                    </td>
                    <td className="px-4 py-3">
                      {g.status === 'FINISHED' && (
                        <button
                          onClick={() => exportCsv(g.id)}
                          className="text-xs px-3 py-1 bg-slate-800 hover:bg-slate-700 border border-slate-600 rounded transition-colors cursor-pointer"
                        >
                          CSV
                        </button>
                      )}
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
