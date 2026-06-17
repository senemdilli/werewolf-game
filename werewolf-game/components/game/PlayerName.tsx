'use client'

import React from 'react'

export const COLOR_MAP: Record<string, string> = {
  Red: '#f87171',       // bright red
  Blue: '#60a5fa',      // bright blue
  Green: '#4ade80',     // bright green
  Yellow: '#facc15',    // bright yellow
  Purple: '#c084fc',    // bright purple
  Orange: '#fb923c',    // bright orange
  Pink: '#f472b6',      // bright pink
  Brown: '#d97706',      // legible amber/brown
  Gray: '#94a3b8',      // slate/gray
  White: '#ffffff',     // white
  Violet: '#a78bfa',    // violet
  Teal: '#2dd4bf',      // teal/turquoise
  Gold: '#fbbf24',      // gold
  Mint: '#6ee7b7',      // mint
  Lavender: '#e9d5ff',  // lavender
}

export function getPlayerColor(name: string): string | undefined {
  if (!name) return undefined
  // Extract color name if name contains "(you)" or similar
  const cleanName = name.replace(/\s*\(you\)\s*/i, '').trim()
  return COLOR_MAP[cleanName]
}

export function getPlayerStyle(name: string): React.CSSProperties {
  const color = getPlayerColor(name)
  return color ? { color } : {}
}

interface PlayerNameProps {
  name: string
  role?: string | null
  isMe?: boolean
  isHost?: boolean
  isMayor?: boolean
  showTeammateIcon?: boolean
}

export default function PlayerName({
  name,
  role,
  isMe,
  isHost,
  isMayor,
  showTeammateIcon = true,
}: PlayerNameProps) {
  const style = getPlayerStyle(name)

  return (
    <span className="inline-flex items-center gap-1">
      <span style={style} className="font-semibold">
        {name}
      </span>
      {isMe && <span className="text-xs text-slate-500 font-normal ml-0.5">(you)</span>}
      {isHost && <span className="text-xs text-violet-400 font-semibold ml-0.5">host</span>}
      {isMayor && <span className="text-xs text-violet-300 font-semibold ml-0.5">👑 mayor</span>}
      {showTeammateIcon && role === 'werewolf' && (
        <span className="text-xs ml-0.5" title="Werewolf teammate">🐺</span>
      )}
    </span>
  )
}
