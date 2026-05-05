import type { Role, Player, Winner } from '@/types/game'

export function assignRoles(players: Player[]): { players: Player[]; mayorId: string | null } {
  const count = players.length
  const roles = buildRoleList(count)
  const shuffled = roles.sort(() => Math.random() - 0.5)
  const assigned = players.map((p, i) => ({ ...p, role: shuffled[i] }))
  const mayor = assigned.find(p => p.role === 'mayor')
  return { players: assigned, mayorId: mayor?.id ?? null }
}

function buildRoleList(count: number): Role[] {
  const roles: Role[] = []

  const werewolves = count <= 5 ? 1 : count <= 8 ? 2 : Math.floor(count / 4)
  for (let i = 0; i < werewolves; i++) roles.push('werewolf')

  roles.push('seer')
  roles.push('mayor')
  if (count >= 6) roles.push('doctor')

  while (roles.length < count) roles.push('villager')

  return roles
}

export function checkWinCondition(players: Player[]): Winner {
  const alive = players.filter(p => p.isAlive)
  const wolves = alive.filter(p => p.role === 'werewolf')
  const others = alive.filter(p => p.role !== 'werewolf')

  if (wolves.length === 0) return 'villagers'
  if (wolves.length >= others.length) return 'werewolves'
  return null
}

export function resolveNightKill(
  werewolfVotes: Record<string, string>,
  doctorTarget: string | null
): { killTargetId: string | null; savedByDoctor: boolean } {
  const voteCounts: Record<string, number> = {}
  for (const targetId of Object.values(werewolfVotes)) {
    voteCounts[targetId] = (voteCounts[targetId] || 0) + 1
  }

  const sorted = Object.entries(voteCounts).sort((a, b) => b[1] - a[1])
  if (sorted.length === 0) return { killTargetId: null, savedByDoctor: false }

  const killTargetId = sorted[0][0]
  const savedByDoctor = killTargetId === doctorTarget

  return { killTargetId: savedByDoctor ? null : killTargetId, savedByDoctor }
}

export function resolveDayVote(
  votes: Record<string, string>,
  mayorId: string | null
): string | null {
  const voteCounts: Record<string, number> = {}
  for (const [voterId, targetId] of Object.entries(votes)) {
    const weight = voterId === mayorId ? 2 : 1
    voteCounts[targetId] = (voteCounts[targetId] || 0) + weight
  }

  const sorted = Object.entries(voteCounts).sort((a, b) => b[1] - a[1])
  if (sorted.length === 0) return null
  if (sorted.length >= 2 && sorted[0][1] === sorted[1][1]) return null

  return sorted[0][0]
}

export const ROLE_INFO: Record<Role, { label: string; color: string; description: string }> = {
  werewolf: {
    label: 'Werewolf',
    color: 'red',
    description: 'Each night, vote with your pack to eliminate a villager. During the day, blend in and avoid suspicion.',
  },
  villager: {
    label: 'Villager',
    color: 'blue',
    description: 'You have no special ability. Use logic, observation, and persuasion to identify and eliminate the werewolves.',
  },
  seer: {
    label: 'Seer',
    color: 'amber',
    description: 'Each night, secretly investigate one player to learn whether they are a Werewolf or not.',
  },
  doctor: {
    label: 'Doctor',
    color: 'green',
    description: 'Each night, choose one player to protect from the werewolves\' attack (you may protect yourself).',
  },
  mayor: {
    label: 'Mayor',
    color: 'violet',
    description: 'Your identity is public — everyone knows you are the Mayor. Your vote counts double during village elections.',
  },
}
