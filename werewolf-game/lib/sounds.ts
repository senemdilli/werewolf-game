'use client'

// Tiny Web Audio cue helper. No audio assets — every cue is synthesized so
// there's nothing to bundle or license. Cues are deliberately short and
// distinguishable by pitch + envelope.
//
// Browsers require a user gesture before audio can start; we lazily create
// (and try to resume()) the AudioContext on every play. Calls before the
// first interaction are silently no-ops.

export type Cue =
  | 'phase-night'
  | 'phase-day'
  | 'vote-open'
  | 'your-turn'
  | 'dawn'
  | 'vote-result'
  | 'chat-msg'

const MUTE_KEY = 'wolf-mute'
const CHAT_PING_COOLDOWN_MS = 2000

let ctx: AudioContext | null = null
let lastChatPingAt = 0
const muteListeners = new Set<(muted: boolean) => void>()

function getCtx(): AudioContext | null {
  if (typeof window === 'undefined') return null
  if (!ctx) {
    const Ctor =
      (window as unknown as { AudioContext?: typeof AudioContext; webkitAudioContext?: typeof AudioContext }).AudioContext ??
      (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext
    if (!Ctor) return null
    try { ctx = new Ctor() } catch { return null }
  }
  if (ctx.state === 'suspended') void ctx.resume().catch(() => {})
  return ctx
}

export function isMuted(): boolean {
  if (typeof window === 'undefined') return false
  return window.localStorage.getItem(MUTE_KEY) === '1'
}

export function setMuted(muted: boolean): void {
  if (typeof window === 'undefined') return
  window.localStorage.setItem(MUTE_KEY, muted ? '1' : '0')
  for (const l of muteListeners) l(muted)
}

export function subscribeMute(listener: (muted: boolean) => void): () => void {
  muteListeners.add(listener)
  return () => { muteListeners.delete(listener) }
}

// One tone with an ADSR-ish envelope.
function tone(
  c: AudioContext,
  freq: number,
  startOffset: number,
  durationSec: number,
  peakGain: number,
  type: OscillatorType = 'sine',
) {
  const t0 = c.currentTime + startOffset
  const t1 = t0 + durationSec
  const osc = c.createOscillator()
  const gain = c.createGain()
  osc.type = type
  osc.frequency.value = freq
  gain.gain.setValueAtTime(0, t0)
  gain.gain.linearRampToValueAtTime(peakGain, t0 + Math.min(0.015, durationSec * 0.2))
  gain.gain.exponentialRampToValueAtTime(0.0001, t1)
  osc.connect(gain).connect(c.destination)
  osc.start(t0)
  osc.stop(t1 + 0.02)
}

export function play(cue: Cue): void {
  if (isMuted()) return
  if (cue === 'chat-msg') {
    const now = Date.now()
    if (now - lastChatPingAt < CHAT_PING_COOLDOWN_MS) return
    lastChatPingAt = now
  }
  const c = getCtx()
  if (!c) return

  switch (cue) {
    case 'phase-night':
      // Low descending pair — "lights out"
      tone(c, 320, 0.00, 0.22, 0.18, 'triangle')
      tone(c, 220, 0.18, 0.32, 0.18, 'triangle')
      break
    case 'phase-day':
      // Bright ascending pair — "lights on"
      tone(c, 520, 0.00, 0.18, 0.16, 'triangle')
      tone(c, 720, 0.14, 0.26, 0.16, 'triangle')
      break
    case 'vote-open':
      // Sharp double-ding
      tone(c, 880, 0.00, 0.12, 0.20, 'square')
      tone(c, 1180, 0.10, 0.14, 0.18, 'square')
      break
    case 'your-turn':
      // Three-pulse attention beep
      tone(c, 660, 0.00, 0.10, 0.22, 'sine')
      tone(c, 660, 0.14, 0.10, 0.22, 'sine')
      tone(c, 990, 0.28, 0.16, 0.22, 'sine')
      break
    case 'dawn':
      // Ascending triad — "morning"
      tone(c, 523, 0.00, 0.18, 0.14, 'triangle')
      tone(c, 659, 0.12, 0.20, 0.14, 'triangle')
      tone(c, 784, 0.24, 0.34, 0.16, 'triangle')
      break
    case 'vote-result':
      // Medium gong-like hit
      tone(c, 196, 0.00, 0.55, 0.20, 'sine')
      tone(c, 294, 0.00, 0.45, 0.10, 'sine')
      break
    case 'chat-msg':
      // Very subtle blip
      tone(c, 1320, 0.00, 0.06, 0.06, 'sine')
      break
  }
}
