# syntax=docker/dockerfile:1.4

FROM node:20-alpine AS base
ENV PNPM_HOME=/root/.local/share/pnpm
ENV PATH="$PNPM_HOME:$PATH"

FROM base AS deps
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1
RUN corepack enable
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY vendor ./vendor
RUN pnpm install --frozen-lockfile

FROM base AS builder
WORKDIR /app
ARG NEXT_PUBLIC_API_BASE_URL
ENV NEXT_TELEMETRY_DISABLED=1 \
    NEXT_PUBLIC_API_BASE_URL=${NEXT_PUBLIC_API_BASE_URL}
COPY --from=deps /root/.local/share/pnpm/store /root/.local/share/pnpm/store
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN corepack enable
RUN mkdir -p public && pnpm run build

FROM base AS runner
WORKDIR /app
ARG NEXT_PUBLIC_API_BASE_URL
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    WEB_PORT=5173 \
    NEXT_PUBLIC_API_BASE_URL=${NEXT_PUBLIC_API_BASE_URL}
COPY --from=deps /root/.local/share/pnpm/store /root/.local/share/pnpm/store
COPY --from=deps /app/node_modules ./node_modules
COPY pnpm-lock.yaml package.json ./
RUN corepack enable && pnpm prune --prod
COPY --from=builder /app/public ./public
COPY --from=builder /app/.next ./.next

EXPOSE 5173

CMD ["sh", "-c", "npm run start -- --hostname 0.0.0.0 --port ${WEB_PORT}"]
