import { NextRequest, NextResponse } from 'next/server'
import { prisma } from '@/lib/prisma'
import { redis } from '@/lib/redis'

// POST /api/admin/games/[gameId] -> Terminate active game (marks as CANCELED, clears Redis, kicks players)
export async function POST(
  req: NextRequest,
  { params }: { params: Promise<{ gameId: string }> }
) {
  try {
    const { gameId } = await params

    const game = await prisma.game.findUnique({
      where: { id: gameId },
      select: { roomCode: true, status: true },
    })

    if (!game) {
      return NextResponse.json({ error: 'Game not found' }, { status: 404 })
    }

    // Update status to CANCELED in DB
    const updatedGame = await prisma.game.update({
      where: { id: gameId },
      data: {
        status: 'CANCELED',
        endedAt: new Date(),
      },
    })

    // Clear active Redis state
    await redis.del(`game:${game.roomCode}`)

    // Kick all active players connected to the socket room
    const io = (global as any).io
    if (io) {
      io.to(`room:${game.roomCode}`).emit(
        'room:kicked',
        'This game has been terminated by the administrator.'
      )
    }

    return NextResponse.json({ success: true, game: updatedGame })
  } catch (err) {
    console.error('Failed to terminate game:', err)
    return NextResponse.json({ error: 'Failed to terminate game' }, { status: 500 })
  }
}

// PATCH /api/admin/games/[gameId] -> Toggle archive state of a game
export async function PATCH(
  req: NextRequest,
  { params }: { params: Promise<{ gameId: string }> }
) {
  try {
    const { gameId } = await params
    const body = await req.json()
    const isArchived = !!body.isArchived

    const game = await prisma.game.findUnique({
      where: { id: gameId },
      select: { roomCode: true, status: true },
    })

    if (!game) {
      return NextResponse.json({ error: 'Game not found' }, { status: 404 })
    }

    // Update archived status in DB
    // If archiving an active game, also mark it as CANCELED
    const updateData: any = { isArchived }
    if (isArchived && game.status === 'IN_PROGRESS') {
      updateData.status = 'CANCELED'
      updateData.endedAt = new Date()
    }

    const updatedGame = await prisma.game.update({
      where: { id: gameId },
      data: updateData,
    })

    // If archiving and active, clear Redis and kick sockets
    if (isArchived) {
      await redis.del(`game:${game.roomCode}`)
      const io = (global as any).io
      if (io) {
        io.to(`room:${game.roomCode}`).emit(
          'room:kicked',
          'This game has been archived by the administrator.'
        )
      }
    }

    return NextResponse.json({ success: true, game: updatedGame })
  } catch (err) {
    console.error('Failed to toggle archive state:', err)
    return NextResponse.json({ error: 'Failed to update archive state' }, { status: 500 })
  }
}

// DELETE /api/admin/games/[gameId] -> Hard delete game and related records
export async function DELETE(
  req: NextRequest,
  { params }: { params: Promise<{ gameId: string }> }
) {
  try {
    const { gameId } = await params

    const game = await prisma.game.findUnique({
      where: { id: gameId },
      select: { roomCode: true },
    })

    if (!game) {
      return NextResponse.json({ error: 'Game not found' }, { status: 404 })
    }

    // Clear active Redis state
    await redis.del(`game:${game.roomCode}`)

    // Kick all active sockets
    const io = (global as any).io
    if (io) {
      io.to(`room:${game.roomCode}`).emit(
        'room:kicked',
        'This game has been deleted by the administrator.'
      )
    }

    // Delete from DB (onDelete: Cascade relations will automatically handle child tables)
    await prisma.game.delete({
      where: { id: gameId },
    })

    return NextResponse.json({ success: true })
  } catch (err) {
    console.error('Failed to delete game:', err)
    return NextResponse.json({ error: 'Failed to delete game' }, { status: 500 })
  }
}
