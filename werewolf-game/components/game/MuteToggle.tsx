'use client'

import { useEffect, useState } from 'react'
import { isMuted, setMuted, subscribeMute, play } from '@/lib/sounds'

export default function MuteToggle() {
  // Start with a stable SSR value, then sync to localStorage on mount.
  const [muted, setLocalMuted] = useState(false)

  useEffect(() => {
    setLocalMuted(isMuted())
    return subscribeMute(setLocalMuted)
  }, [])

  function toggle() {
    const next = !muted
    setMuted(next)
    // Confirm-on-unmute so the user knows audio works (and to satisfy the
    // browser's user-gesture requirement for the AudioContext).
    if (!next) play('your-turn')
  }

  return (
    <button
      onClick={toggle}
      title={muted ? 'Unmute game sounds' : 'Mute game sounds'}
      aria-label={muted ? 'Unmute game sounds' : 'Mute game sounds'}
      className="text-slate-400 hover:text-slate-200 text-sm px-2 py-1 rounded cursor-pointer"
    >
      {muted ? '🔇' : '🔊'}
    </button>
  )
}
