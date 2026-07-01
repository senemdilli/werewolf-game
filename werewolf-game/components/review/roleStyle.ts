// Shared styling helpers for the review dashboard. Roles in the exports are
// uppercase (WEREWOLF | VILLAGER | SEER | WITCH).

export function roleBadgeClass(role: string): string {
  switch (role.toUpperCase()) {
    case 'WEREWOLF':
      return 'text-red-300 bg-red-950/50 border-red-800'
    case 'SEER':
      return 'text-amber-300 bg-amber-950/50 border-amber-800'
    case 'WITCH':
      return 'text-purple-300 bg-purple-950/50 border-purple-800'
    case 'VILLAGER':
      return 'text-blue-300 bg-blue-950/50 border-blue-800'
    default:
      return 'text-slate-300 bg-slate-800 border-slate-700'
  }
}

export function roleLabel(role: string): string {
  if (!role) return ''
  return role.charAt(0).toUpperCase() + role.slice(1).toLowerCase()
}

// 1..7 trust score → a red(low)→amber→green(high) class pair (text + bg border).
export function scoreClass(score: number): string {
  if (score <= 2) return 'text-red-300 bg-red-950/40 border-red-800/60'
  if (score <= 3) return 'text-orange-300 bg-orange-950/40 border-orange-800/60'
  if (score === 4) return 'text-slate-300 bg-slate-800/60 border-slate-700'
  if (score <= 6) return 'text-lime-300 bg-lime-950/40 border-lime-800/60'
  return 'text-emerald-300 bg-emerald-950/40 border-emerald-800/60'
}

export function confidenceLabel(confidence: string): string {
  return confidence ? confidence.toLowerCase() : ''
}
