import { prisma } from '@/lib/prisma'
import { NextRequest } from 'next/server'

export async function GET(req: NextRequest) {
  const { searchParams } = new URL(req.url)
  const page = parseInt(searchParams.get('page') || '1', 10)
  const limit = 20
  const skip = (page - 1) * limit

  const [games, total] = await Promise.all([
    prisma.game.findMany({
      orderBy: { createdAt: 'desc' },
      skip,
      take: limit,
      include: {
        _count: { select: { messages: true, players: true } },
      },
    }),
    prisma.game.count(),
  ])

  return Response.json({ games, total, page, pages: Math.ceil(total / limit) })
}
