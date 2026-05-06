import Link from 'next/link'

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
      'You hold two single-use potions. The heal potion saves the werewolves\' nightly victim; the kill potion lets you eliminate any player of your choice. Use them wisely — each can only be used once per game.',
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
  {
    icon: '👑',
    name: 'Mayor',
    color: 'border-yellow-600 bg-yellow-950/40',
    nameColor: 'text-yellow-300',
    team: 'Elected role (any team)',
    teamColor: 'text-yellow-500',
    description:
      'Elected by vote on the first morning. The Mayor\'s vote counts double in day votes, breaking ties. The Mayor retains the role until eliminated — beware, werewolves will want them gone.',
  },
]

const phases = [
  {
    icon: '🏠',
    name: 'Lobby',
    description: 'Players join via room code and mark themselves ready. The game starts automatically once everyone is ready (minimum 4 players). The host can force-start at any time.',
  },
  {
    icon: '🃏',
    name: 'Role Reveal',
    description: 'Each player privately sees their assigned role. Acknowledge your role when ready — once everyone has, the first night begins.',
  },
  {
    icon: '🌙',
    name: 'Night',
    description: 'Everyone "sleeps". Werewolves pick a victim. The Seer investigates one player. The Witch decides whether to save the victim and/or poison someone. Actions are secret.',
  },
  {
    icon: '🗳️',
    name: 'Mayor Election',
    description: 'On the first morning only, players vote to elect a Mayor. The candidate with the most votes wins. The Mayor\'s day vote counts double for the rest of the game.',
  },
  {
    icon: '☀️',
    name: 'Day Discussion',
    description: 'The night\'s victim (if any) is revealed and eliminated. All surviving players discuss, debate, and try to identify the werewolves. Use the chat — make your case.',
  },
  {
    icon: '⚖️',
    name: 'Day Vote',
    description: 'Players vote to eliminate a suspect. Majority rules. If the Mayor is alive, their vote counts double. The eliminated player\'s role is revealed to everyone.',
  },
]

const rules = [
  { rule: 'Minimum 4 players to start a game.' },
  { rule: 'Dead players cannot send messages or vote.' },
  { rule: 'Werewolves can see each other\'s names in the night chat.' },
  { rule: 'The Seer only learns "werewolf" or "not a werewolf" — not the exact role.' },
  { rule: 'The Witch can see who the werewolves targeted before deciding whether to heal.' },
  { rule: 'Each Witch potion (heal & kill) can only be used once per game.' },
  { rule: 'Mayor election happens once — on the first morning.' },
  { rule: 'The Mayor role persists until that player is eliminated.' },
  { rule: 'If a vote ends in a tie, no one is eliminated that day.' },
  { rule: 'Eliminated players\' roles are always revealed to everyone.' },
]

export default function HowToPlay() {
  return (
    <div className="min-h-screen px-4 py-12 max-w-2xl mx-auto">
      <div className="mb-10">
        <Link href="/" className="text-slate-500 hover:text-slate-300 text-sm transition-colors">
          ← Back to home
        </Link>
      </div>

      <div className="text-center mb-12">
        <div className="text-6xl mb-4">🐺</div>
        <h1 className="text-3xl font-black text-slate-100">How to Play Werewolf</h1>
        <p className="text-slate-400 mt-2">A social deduction game of trust, lies, and survival</p>
      </div>

      {/* Goal */}
      <section className="mb-10">
        <h2 className="text-lg font-bold text-slate-100 mb-4 uppercase tracking-wide">The Goal</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div className="bg-blue-950/40 border border-blue-800 rounded-xl p-4">
            <p className="text-blue-300 font-semibold mb-1">🏘️ Villagers win when…</p>
            <p className="text-slate-300 text-sm">all werewolves have been eliminated by day vote or the Witch's kill potion.</p>
          </div>
          <div className="bg-red-950/40 border border-red-800 rounded-xl p-4">
            <p className="text-red-300 font-semibold mb-1">🐺 Werewolves win when…</p>
            <p className="text-slate-300 text-sm">their numbers equal or outnumber the remaining villagers — the village can no longer vote them out.</p>
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
        </div>
      </section>

      {/* Game Flow */}
      <section className="mb-10">
        <h2 className="text-lg font-bold text-slate-100 mb-4 uppercase tracking-wide">Game Flow</h2>
        <div className="space-y-2">
          {phases.map((p, i) => (
            <div key={p.name} className="flex gap-4 items-start bg-slate-900 border border-slate-700 rounded-xl p-4">
              <div className="flex flex-col items-center shrink-0">
                <span className="text-2xl">{p.icon}</span>
                {i < phases.length - 1 && (
                  <div className="w-px h-4 bg-slate-700 mt-1" />
                )}
              </div>
              <div>
                <p className="font-semibold text-slate-200 text-sm">{p.name}</p>
                <p className="text-slate-400 text-sm mt-0.5 leading-relaxed">{p.description}</p>
              </div>
            </div>
          ))}
        </div>
        <p className="text-slate-500 text-xs mt-3 text-center">Night → Mayor Election (round 1 only) → Day Discussion → Day Vote → repeat until someone wins.</p>
      </section>

      {/* Rules */}
      <section className="mb-12">
        <h2 className="text-lg font-bold text-slate-100 mb-4 uppercase tracking-wide">Rules</h2>
        <ul className="space-y-2">
          {rules.map((r, i) => (
            <li key={i} className="flex gap-3 text-sm text-slate-300">
              <span className="text-slate-600 shrink-0 font-mono">{String(i + 1).padStart(2, '0')}</span>
              {r.rule}
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
