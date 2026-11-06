# Next.js standalone image. Build context: ./frontend (see docker-compose.yml).
FROM node:22-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

FROM node:22-alpine AS build
WORKDIR /app
# The browser calls the backend at this URL. Next.js inlines it at build time.
ARG NEXT_PUBLIC_API_URL
# Empty timeouts fall back to the defaults in src/lib/config.ts.
ARG NEXT_PUBLIC_API_TIMEOUT_MS=""
ARG NEXT_PUBLIC_STREAM_IDLE_TIMEOUT_MS=""
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL} \
    NEXT_PUBLIC_API_TIMEOUT_MS=${NEXT_PUBLIC_API_TIMEOUT_MS} \
    NEXT_PUBLIC_STREAM_IDLE_TIMEOUT_MS=${NEXT_PUBLIC_STREAM_IDLE_TIMEOUT_MS} \
    NEXT_TELEMETRY_DISABLED=1
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

FROM node:22-alpine AS run
WORKDIR /app
# server.js reads PORT at runtime. Compose sets it from FRONTEND_PORT.
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    HOSTNAME=0.0.0.0
COPY --from=build --chown=node:node /app/public ./public
COPY --from=build --chown=node:node /app/.next/standalone ./
COPY --from=build --chown=node:node /app/.next/static ./.next/static
USER node
CMD ["node", "server.js"]
