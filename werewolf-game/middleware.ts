import { NextRequest, NextResponse } from 'next/server'

const ADMIN_PATHS = ['/admin', '/api/admin']

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl

  const isAdminPath = ADMIN_PATHS.some(p => pathname === p || pathname.startsWith(p + '/'))
  if (!isAdminPath) return NextResponse.next()

  // Allow the login page and auth endpoint through without cookie check
  if (pathname === '/admin/login' || pathname === '/api/admin/auth') {
    return NextResponse.next()
  }

  const token = request.cookies.get('admin_token')?.value
  const secret = process.env.ADMIN_SECRET

  if (!secret || token !== secret) {
    if (pathname.startsWith('/api/')) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
    }
    const loginUrl = new URL('/admin/login', request.url)
    return NextResponse.redirect(loginUrl)
  }

  return NextResponse.next()
}

export const config = {
  matcher: ['/admin/:path*', '/api/admin/:path*'],
}
