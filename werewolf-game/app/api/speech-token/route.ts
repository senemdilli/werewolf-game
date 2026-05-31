import { NextResponse } from 'next/server'

export async function GET() {
  try {
    const masterKey = process.env.DEEPGRAM_API_KEY
    if (!masterKey) {
      return NextResponse.json(
        { error: 'Deepgram API key is not configured' },
        { status: 500 }
      )
    }

    // 1. Fetch projects to find the Project ID
    const projectsResponse = await fetch('https://api.deepgram.com/v1/projects', {
      headers: { 'Authorization': `Token ${masterKey}` }
    })

    if (!projectsResponse.ok) {
      // Fallback: return master key if we can't fetch projects (e.g. key has limited scopes)
      return NextResponse.json({ token: masterKey })
    }

    const projectsData = await projectsResponse.json()
    const projectId = projectsData.projects?.[0]?.project_id

    if (!projectId) {
      return NextResponse.json({ token: masterKey })
    }

    // 2. Generate a short-lived temporary key (60 seconds time-to-live)
    const keyResponse = await fetch(`https://api.deepgram.com/v1/projects/${projectId}/keys`, {
      method: 'POST',
      headers: {
        'Authorization': `Token ${masterKey}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        comment: 'Temporary client key for real-time WebSockets',
        scopes: ['usage:write'],
        time_to_live_in_seconds: 60
      })
    })

    if (!keyResponse.ok) {
      return NextResponse.json({ token: masterKey })
    }

    const keyData = await keyResponse.json()
    return NextResponse.json({ token: keyData.key })
  } catch (err: any) {
    console.error('Error generating short-lived Deepgram token:', err)
    // Safe fallback to master key
    return NextResponse.json({ token: process.env.DEEPGRAM_API_KEY })
  }
}
