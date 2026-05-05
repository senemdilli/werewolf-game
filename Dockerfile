FROM node:20-alpine AS base
WORKDIR /app
COPY package*.json ./

FROM base AS deps
RUN npm ci

FROM base AS builder
COPY --from=deps /app/node_modules ./node_modules
COPY . .
# DATABASE_URL required by prisma.config.ts at generate time — dummy is fine, no connection made
ARG DATABASE_URL="postgresql://dummy:dummy@localhost:5432/dummy"
ENV DATABASE_URL=$DATABASE_URL
RUN npx prisma generate
RUN npm run build

FROM base AS runner
ENV NODE_ENV=production
# Copy entire build context — Next.js 16 App Router needs source files at runtime alongside .next
COPY --from=builder /app ./

RUN npm install -g tsx

EXPOSE 3000

CMD ["sh", "-c", "npx prisma db push --accept-data-loss && tsx server.ts"]
