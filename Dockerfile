FROM node:20-alpine AS base
WORKDIR /app
COPY package*.json ./

FROM base AS deps
RUN npm ci

FROM base AS builder
COPY --from=deps /app/node_modules ./node_modules
COPY . .
# DATABASE_URL is required by prisma.config.ts at generate time — dummy value is fine, no connection is made
ARG DATABASE_URL="postgresql://dummy:dummy@localhost:5432/dummy"
ENV DATABASE_URL=$DATABASE_URL
RUN npx prisma generate
RUN npm run build

FROM base AS runner
ENV NODE_ENV=production
# Use node_modules from builder (includes generated Prisma client)
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/public ./public
COPY --from=builder /app/prisma ./prisma
COPY --from=builder /app/prisma.config.ts ./prisma.config.ts
COPY --from=builder /app/server ./server
COPY --from=builder /app/lib ./lib
COPY --from=builder /app/types ./types
COPY --from=builder /app/server.ts ./server.ts
COPY --from=builder /app/tsconfig.json ./tsconfig.json
COPY package*.json ./

RUN npm install -g tsx

EXPOSE 3000

CMD ["sh", "-c", "npx prisma db push --accept-data-loss && tsx server.ts"]
