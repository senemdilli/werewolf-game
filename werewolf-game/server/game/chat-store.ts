import { redis } from '@/lib/redis'
import type { ChatMessage, Role } from '@/types/game'

const CHAT_TTL = 60 * 60 * 24 // 24 hours

export async function getChatHistory(roomCode: string): Promise<ChatMessage[]> {
  try {
    const raw = await redis.get(`chat:${roomCode}`)
    if (!raw) return []
    return JSON.parse(raw) as ChatMessage[]
  } catch (err) {
    console.error('[getChatHistory]', err)
    return []
  }
}

export async function saveChatHistory(roomCode: string, messages: ChatMessage[]): Promise<void> {
  try {
    await redis.set(`chat:${roomCode}`, JSON.stringify(messages), 'EX', CHAT_TTL)
  } catch (err) {
    console.error('[saveChatHistory]', err)
  }
}

export async function addChatMessage(roomCode: string, message: ChatMessage): Promise<void> {
  try {
    const history = await getChatHistory(roomCode)
    history.push(message)
    await saveChatHistory(roomCode, history)
  } catch (err) {
    console.error('[addChatMessage]', err)
  }
}

export async function clearChatHistory(roomCode: string): Promise<void> {
  try {
    await redis.del(`chat:${roomCode}`)
  } catch (err) {
    console.error('[clearChatHistory]', err)
  }
}

// Players see only the current round's chat. Persistence keeps everything; this
// is purely the live view filter (also enforces the night-chat wolves-only rule).
export function filterChatForPlayer(
  history: ChatMessage[],
  currentRound: number,
  playerRole: Role | null,
): ChatMessage[] {
  return history.filter(msg => {
    if (msg.round !== currentRound) return false
    if (msg.isSystem) return true
    if (msg.phase === 'night') return playerRole === 'werewolf'
    return true
  })
}
