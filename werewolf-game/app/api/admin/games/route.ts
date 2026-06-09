import { prisma } from '@/lib/prisma'
import { NextRequest } from 'next/server'

export async function GET(req: NextRequest) {
  const { searchParams } = new URL(req.url)
  const page = parseInt(searchParams.get('page') || '1', 10)
  const limit = 20
  const skip = (page - 1) * limit

  const type = searchParams.get('type') || 'all'
  const showArchived = searchParams.get('archived') === 'true'

  // 1. Lazy cleanup: Auto-cancel games in progress started more than 24h ago
  try {
    const oneDayAgo = new Date(Date.now() - 24 * 60 * 60 * 1000)
    await prisma.game.updateMany({
      where: {
        status: 'IN_PROGRESS',
        createdAt: { lt: oneDayAgo },
      },
      data: {
        status: 'CANCELED',
        endedAt: new Date(),
      },
    })
  } catch (err) {
    console.error('Failed to run lazy stale game cleanup:', err)
  }

  // 2. Build where filter
  const where: any = {
    isArchived: showArchived,
  }

  if (type === 'sandbox') {
    where.isSandbox = true
  } else if (type === 'normal') {
    where.isSandbox = false
  }

  const [games, total] = await Promise.all([
    prisma.game.findMany({
      where,
      orderBy: { createdAt: 'desc' },
      skip,
      take: limit,
      include: {
        _count: { select: { messages: true, players: true } },
      },
    }),
    prisma.game.count({ where }),
  ])

  return Response.json({ games, total, page, pages: Math.ceil(total / limit) })
}
