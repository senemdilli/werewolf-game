'use client'

import { useEffect, useRef, useState } from 'react'
import {
  isMuted, setMuted, subscribeMute,
  getVolume, setVolume, subscribeVolume,
  play,
} from '@/lib/sounds'

export default function MuteToggle() {
  // Start with stable SSR values, then sync to localStorage on mount.
  const [muted, setLocalMuted] = useState(false)
  const [volume, setLocalVolume] = useState(0.6)
  const [open, setOpen] = useState(false)
  const wrapperRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    setLocalMuted(isMuted())
    setLocalVolume(getVolume())
    const unsubM = subscribeMute(setLocalMuted)
    const unsubV = subscribeVolume(setLocalVolume)
    return () => { unsubM(); unsubV() }
  }, [])

  // Close the popover on outside click.
  useEffect(() => {
    if (!open) return
    function onDown(e: MouseEvent) {
      if (!wrapperRef.current?.contains(e.target as Node)) setOpen(false)
    }
    window.addEventListener('mousedown', onDown)
    return () => window.removeEventListener('mousedown', onDown)
  }, [open])

  function toggleMute() {
    const next = !muted
    setMuted(next)
    // Confirm-on-unmute (also satisfies the browser's user-gesture
    // requirement for the AudioContext).
    if (!next) play('your-turn')
  }

  function onSlider(e: React.ChangeEvent<HTMLInputElement>) {
    const v = Number(e.target.value) / 100
    setVolume(v)
  }

  function previewVolume() {
    // Tiny chirp so the user hears the new level while dragging stops.
    if (!muted) play('chat-msg')
  }

  function handleIconClick() {
    // Opening the panel is the user's first explicit sound interaction —
    // play a near-silent cue to unlock the AudioContext (autoplay policy
    // requires resume() inside a user gesture). No audible side effect when
    // muted because play() short-circuits.
    if (!open && !muted) play('chat-msg')
    setOpen(o => !o)
  }

  return (
    <div ref={wrapperRef} className="relative">
      <button
        onClick={handleIconClick}
        title="Sound settings"
        aria-label="Sound settings"
        className="text-slate-400 hover:text-slate-200 text-sm px-2 py-1 rounded cursor-pointer"
      >
        {muted || volume === 0 ? '🔇' : volume < 0.4 ? '🔈' : volume < 0.75 ? '🔉' : '🔊'}
      </button>

      {open && (
        <div className="absolute top-full left-0 mt-1 bg-slate-900/95 border border-slate-700 rounded-lg shadow-lg p-3 flex flex-col gap-2 w-56 z-50">
          <div className="flex items-center justify-between text-xs text-slate-300">
            <span className="font-semibold">Sound</span>
            <button
              onClick={toggleMute}
              className="text-[11px] px-2 py-0.5 rounded border border-slate-700 hover:border-slate-500 text-slate-300 cursor-pointer"
            >
              {muted ? 'Unmute' : 'Mute'}
            </button>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-xs text-slate-500 w-8">{Math.round(volume * 100)}%</span>
            <input
              type="range"
              min={0}
              max={100}
              step={1}
              value={Math.round(volume * 100)}
              onChange={onSlider}
              onMouseUp={previewVolume}
              onTouchEnd={previewVolume}
              disabled={muted}
              aria-label="Sound volume"
              className="flex-1 accent-amber-500 cursor-pointer disabled:opacity-40"
            />
          </div>
        </div>
      )}
    </div>
  )
}
