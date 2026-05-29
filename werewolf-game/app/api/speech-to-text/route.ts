import { NextResponse } from 'next/server'

export async function POST(request: Request) {
  try {
    const apiKey = process.env.DEEPGRAM_API_KEY
    if (!apiKey) {
      return NextResponse.json(
        { error: 'Deepgram API key is not configured' },
        { status: 500 }
      )
    }

    const contentType = request.headers.get('content-type') || 'audio/webm'
    const audioBuffer = await request.arrayBuffer()

    const url = new URL('https://api.deepgram.com/v1/listen')
    url.searchParams.set('model', 'nova-2')
    url.searchParams.set('smart_format', 'true')
    url.searchParams.set('language', 'en')

    const response = await fetch(url.toString(), {
      method: 'POST',
      headers: {
        'Authorization': `Token ${apiKey}`,
        'Content-Type': contentType,
      },
      body: audioBuffer,
    })

    if (!response.ok) {
      const errorText = await response.text()
      console.error('Deepgram API error:', errorText)
      return NextResponse.json(
        { error: 'Failed to transcribe audio via Deepgram' },
        { status: response.status }
      )
    }

    const data = await response.json()
    const transcript = data.results?.channels?.[0]?.alternatives?.[0]?.transcript || ''

    return NextResponse.json({ transcript })
  } catch (error: any) {
    console.error('Error in speech-to-text API:', error)
    return NextResponse.json(
      { error: error.message || 'Internal server error' },
      { status: 500 }
    )
  }
}
