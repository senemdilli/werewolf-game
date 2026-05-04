import { createServer } from 'http'
import next from 'next'
import { Server as SocketIOServer } from 'socket.io'
import { setupSocketHandlers } from './server/socket/index'
import type { ServerToClientEvents, ClientToServerEvents } from './types/game'

const port = parseInt(process.env.PORT || '3000', 10)
const dev = process.env.NODE_ENV !== 'production'
const app = next({ dev, port })
const handle = app.getRequestHandler()

app.prepare().then(() => {
  const httpServer = createServer((req, res) => {
    handle(req, res)
  })

  const io = new SocketIOServer<ClientToServerEvents, ServerToClientEvents>(httpServer, {
    cors: {
      origin: process.env.NEXT_PUBLIC_APP_URL || '*',
      methods: ['GET', 'POST'],
    },
  })

  setupSocketHandlers(io)

  httpServer.listen(port, () => {
    console.log(`> Ready on http://localhost:${port} [${dev ? 'dev' : 'prod'}]`)
  })
})
