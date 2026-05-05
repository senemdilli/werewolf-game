import { NextRequest, NextResponse } from 'next/server'

export async function POST(request: NextRequest) {
  const { password } = await request.json()
  const secret = process.env.ADMIN_SECRET

  console.log('[admin/auth] secret defined:', !!secret, '| secret length:', secret?.length, '| password length:', password?.length, '| match:', password === secret)

  if (!secret || password !== secret) {
    return NextResponse.json({ error: 'Invalid password' }, { status: 401 })
  }

  const response = NextResponse.json({ ok: true })
  response.cookies.set('admin_token', secret, {
    httpOnly: true,
    secure: request.url.startsWith('https://'),
    sameSite: 'lax',
    maxAge: 60 * 60 * 8, // 8 hours
    path: '/',
  })
  return response
}

export async function DELETE() {
  const response = NextResponse.json({ ok: true })
  response.cookies.delete('admin_token')
  return response
}
