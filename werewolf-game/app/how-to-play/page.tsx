'use client'

import Link from 'next/link'
import { useState } from 'react'

type Mode = 'classic' | 'arena'

const roles = [
  {
    icon: '🐺',
    name: 'Werewolf',
    color: 'border-red-800 bg-red-950/40',
    nameColor: 'text-red-300',
    team: 'Werewolf team',
    teamColor: 'text-red-400',
    description:
      'Each night, werewolves secretly agree on a villager to eliminate. During the day you must blend in, cast suspicion on others, and avoid being voted out.',
  },
  {
    icon: '👁️',
    name: 'Seer',
    color: 'border-amber-700 bg-amber-950/40',
    nameColor: 'text-amber-300',
    team: 'Villager team',
    teamColor: 'text-blue-400',
    description:
      'Each night you may investigate one player and learn whether they are a werewolf or not. Share your findings carefully — revealing yourself makes you a target.',
  },
  {
    icon: '🧙',
    name: 'Witch',
    color: 'border-purple-700 bg-purple-950/40',
    nameColor: 'text-purple-300',
    team: 'Villager team',
    teamColor: 'text-blue-400',
    description:
      "You hold two single-use potions. The heal potion saves the werewolves' nightly victim; the kill potion lets you eliminate any player of your choice. Use them wisely — each can only be used once per game.",
  },
  {
    icon: '👥',
    name: 'Villager',
    color: 'border-slate-600 bg-slate-800/40',
    nameColor: 'text-slate-200',
    team: 'Villager team',
    teamColor: 'text-blue-400',
    description:
      'No special powers — just your voice and your vote. Pay close attention to who speaks with too much certainty, who deflects blame, and who stays suspiciously quiet.',
  },
]

const mayorDescriptions: Record<Mode, string> = {
  classic:
    "Elected on the first morning (and re-elected if killed). The Mayor's day vote counts double, breaking ties. Werewolves will want them gone.",
  arena:
    'Elected after a structured advocacy + discussion phase. In Arena, the Mayor does NOT have a double vote — instead, they break ties at the end of the day vote.',
}

const classicPhases = [
  {
    icon: '🏠',
    name: 'Lobby',
    description:
      'Players join via room code and mark themselves ready. The game starts automatically once everyone is ready (minimum 4 players). The host can force-start at any time.',
  },
  { icon: '🃏', name: 'Role Reveal', description: 'Each player privately sees their assigned role. Acknowledge to continue; once everyone has, the first night begins.' },
  { icon: '🌙', name: 'Night', description: 'Werewolves vote on a victim (free chat among the pack). The Seer investigates one player. The Witch sees the wolves\' target and decides whether to heal and/or use her kill potion.' },
  { icon: '🗳️', name: 'Mayor Election', description: 'First morning only (or after the Mayor dies): everyone votes for a Mayor. Free chat during the election. The Mayor\'s day vote counts double.' },
  { icon: '☀️', name: 'Day Discussion', description: 'Last night\'s outcome is announced. Free chat for ~2 minutes — make accusations, defend yourself, share Seer info if you dare.' },
  { icon: '⚖️', name: 'Day Vote', description: 'Players vote to exile someone, or vote skip. The Mayor\'s vote weighs double. Result is announced on a shared screen, then back to night.' },
]

const arenaPhases = [
  {
    icon: '🏠',
    name: 'Lobby',
    description: 'Same as Classic.',
  },
  { icon: '🃏', name: 'Role Reveal', description: 'Same as Classic.' },
  {
    icon: '🌙',
    name: 'Night (Wolves)',
    description:
      'No talking. With one wolf, they simply pick. With multiple wolves, three rounds of sequential voting in a random order, with all votes visible. Round 3 must be unanimous to kill — otherwise no one dies. Wolves can vote "nobody" to spare everyone.',
  },
  { icon: '🌙', name: 'Night (Witch & Seer)', description: 'The Witch is told whether anyone is under attack. She can heal (if anyone) and/or use her kill potion. The Seer learns one player\'s faction.' },
  {
    icon: '🗳️',
    name: 'Mayor Election (Advocacy)',
    description: 'Held when there is no Mayor. Each living player gets one message in a random order to pitch themselves — 30 seconds each.',
  },
  {
    icon: '💬',
    name: 'Mayor Election (Discussion)',
    description: 'Four bid-to-speak rounds. Every round, players privately bid 1–5; the highest bidder speaks one message (random tiebreak). 10s bid window, 30s speak window.',
  },
  {
    icon: '⚖️',
    name: 'Mayor Vote',
    description: 'Everyone votes (including for yourself, if you wish). Individual votes are published. On tie: runoff between top candidates; if still tied, random pick.',
  },
  {
    icon: '☀️',
    name: 'Day Discussion',
    description: 'Eight bid-to-speak rounds. Same bidding cadence as the mayor discussion. No free-for-all chat — only the bid winner speaks each round.',
  },
  {
    icon: '⚖️',
    name: 'Day Vote',
    description:
      'Players vote to exile someone (or skip). The Mayor\'s vote is weight 1, but: if no one has more than one vote, nobody is exiled; if there is a tie at the top, the Mayor picks one of the tied candidates (or declines, in which case nobody is exiled).',
  },
]

const classicRules = [
  'Minimum 4 players to start a game.',
  'Dead players cannot send messages or vote.',
  'Werewolves see each other\'s names and can chat in a private channel at night.',
  'The Seer only learns "werewolf" or "not a werewolf" — not the exact role.',
  'The Witch can see who the werewolves targeted before deciding whether to heal.',
  'Each Witch potion (heal & kill) can only be used once per game.',
  'Mayor is elected on the first morning and re-elected on the morning after their death.',
  'The Mayor\'s day vote counts as 2.',
  'If a day vote ends in a tie, no one is eliminated that day.',
  'Eliminated players\' roles are always revealed to everyone.',
]

const arenaRules = [
  'Minimum 4 players to start a game.',
  'Dead players don\'t bid, speak, or vote.',
  'No talking during the wolf night vote — wolves coordinate only through their 3 rounds of votes.',
  'Wolves can vote "nobody" — and if they don\'t unanimously agree on the same player at the end of round 3, nobody dies.',
  'Witch is informed whether anyone is under attack and can heal if so; her kill potion is available regardless.',
  'In discussion phases, only the highest bidder speaks each round. Everyone else watches.',
  'Bids are private. Highest bid wins; random tiebreak. Default bid is 1 if you don\'t submit one.',
  'Mayor advocacy gives every player exactly one opening message in a random order.',
  'Mayor vote allows voting for yourself. Individual votes are published. Ties → runoff → random.',
  'Day vote requires more than one vote on a single target to exile. Tied vote → Mayor decides.',
  'The Mayor breaks ties; their vote does NOT count double in Arena mode.',
  'Eliminated players\' roles are always revealed.',
]

export default function HowToPlay() {
  const [mode, setMode] = useState<Mode>('classic')

  const phases = mode === 'classic' ? classicPhases : arenaPhases
  const rules = mode === 'classic' ? classicRules : arenaRules

  return (
    <div className="min-h-screen px-4 py-12 max-w-2xl mx-auto">
      <div className="mb-10">
        <Link href="/" className="text-slate-500 hover:text-slate-300 text-sm transition-colors">
          ← Back to home
        </Link>
      </div>

      <div className="text-center mb-8">
        <div className="text-6xl mb-4">🐺</div>
        <h1 className="text-3xl font-black text-slate-100">How to Play Werewolf</h1>
        <p className="text-slate-400 mt-2">A social deduction game of trust, lies, and survival</p>
      </div>

      {/* Mode toggle */}
      <div className="flex justify-center mb-10">
        <div className="inline-flex rounded-xl border border-slate-700 bg-slate-900 p-1">
          <button
            onClick={() => setMode('classic')}
            className={`px-4 py-2 text-sm font-semibold rounded-lg transition-colors cursor-pointer ${
              mode === 'classic' ? 'bg-violet-600 text-white' : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            Classic
          </button>
          <button
            onClick={() => setMode('arena')}
            className={`px-4 py-2 text-sm font-semibold rounded-lg transition-colors cursor-pointer ${
              mode === 'arena' ? 'bg-amber-600 text-white' : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            Arena
          </button>
        </div>
      </div>

      <p className="text-center text-slate-500 text-sm mb-10">
        {mode === 'classic'
          ? 'The original free-form rules. Pick a name, talk freely, vote, repeat.'
          : (
            <>
              Structured rules adapted from the{' '}
              <span className="text-amber-300">Werewolf Arena</span> paper. Sequential wolf voting, advocacy, bid-to-speak conversation.
            </>
          )}
      </p>

      {/* Goal */}
      <section className="mb-10">
        <h2 className="text-lg font-bold text-slate-100 mb-4 uppercase tracking-wide">The Goal</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div className="bg-blue-950/40 border border-blue-800 rounded-xl p-4">
            <p className="text-blue-300 font-semibold mb-1">🏘️ Villagers win when…</p>
            <p className="text-slate-300 text-sm">all werewolves have been eliminated.</p>
          </div>
          <div className="bg-red-950/40 border border-red-800 rounded-xl p-4">
            <p className="text-red-300 font-semibold mb-1">🐺 Werewolves win when…</p>
            <p className="text-slate-300 text-sm">their numbers equal or outnumber the remaining villagers.</p>
          </div>
        </div>
      </section>

      {/* Roles */}
      <section className="mb-10">
        <h2 className="text-lg font-bold text-slate-100 mb-4 uppercase tracking-wide">Roles</h2>
        <div className="space-y-3">
          {roles.map(r => (
            <div key={r.name} className={`border rounded-xl p-4 ${r.color}`}>
              <div className="flex items-center gap-2 mb-1">
                <span className="text-xl">{r.icon}</span>
                <span className={`font-bold ${r.nameColor}`}>{r.name}</span>
                <span className={`text-xs ml-auto ${r.teamColor}`}>{r.team}</span>
              </div>
              <p className="text-slate-300 text-sm leading-relaxed">{r.description}</p>
            </div>
          ))}
          <div className="border rounded-xl p-4 border-yellow-600 bg-yellow-950/40">
            <div className="flex items-center gap-2 mb-1">
              <span className="text-xl">👑</span>
              <span className="font-bold text-yellow-300">Mayor</span>
              <span className="text-xs ml-auto text-yellow-500">Elected role (any team)</span>
            </div>
            <p className="text-slate-300 text-sm leading-relaxed">{mayorDescriptions[mode]}</p>
          </div>
        </div>
      </section>

      {/* Game Flow */}
      <section className="mb-10">
        <h2 className="text-lg font-bold text-slate-100 mb-4 uppercase tracking-wide">Game Flow ({mode})</h2>
        <div className="space-y-2">
          {phases.map((p, i) => (
            <div key={p.name + i} className="flex gap-4 items-start bg-slate-900 border border-slate-700 rounded-xl p-4">
              <div className="flex flex-col items-center shrink-0">
                <span className="text-2xl">{p.icon}</span>
                {i < phases.length - 1 && <div className="w-px h-4 bg-slate-700 mt-1" />}
              </div>
              <div>
                <p className="font-semibold text-slate-200 text-sm">{p.name}</p>
                <p className="text-slate-400 text-sm mt-0.5 leading-relaxed">{p.description}</p>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Rules */}
      <section className="mb-12">
        <h2 className="text-lg font-bold text-slate-100 mb-4 uppercase tracking-wide">Rules ({mode})</h2>
        <ul className="space-y-2">
          {rules.map((r, i) => (
            <li key={i} className="flex gap-3 text-sm text-slate-300">
              <span className="text-slate-600 shrink-0 font-mono">{String(i + 1).padStart(2, '0')}</span>
              {r}
            </li>
          ))}
        </ul>
      </section>

      <div className="text-center">
        <Link
          href="/"
          className="inline-block px-6 py-3 bg-violet-600 hover:bg-violet-700 text-white font-semibold rounded-xl transition-colors"
        >
          Play now
        </Link>
      </div>
    </div>
  )
}
