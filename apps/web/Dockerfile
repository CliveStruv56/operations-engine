# Web image — built at deploy time (Coolify) because NEXT_PUBLIC_* values are
# inlined into the client bundle at build; pass them as build args per
# environment. CI validates this Dockerfile with dummy args (app-images.yml).
FROM node:22-slim AS build

RUN corepack enable
WORKDIR /app

# patches/ must be present before install: pnpm-workspace.yaml declares
# patchedDependencies (brace-expansion CVE shim — see CLAUDE.md hardening).
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY patches/ patches/
RUN pnpm install --frozen-lockfile

COPY . .

ARG NEXT_PUBLIC_SUPABASE_URL
ARG NEXT_PUBLIC_SUPABASE_ANON_KEY
ARG NEXT_PUBLIC_API_URL
ARG NEXT_PUBLIC_STORAGE_ORIGIN
ENV NEXT_PUBLIC_SUPABASE_URL=$NEXT_PUBLIC_SUPABASE_URL \
    NEXT_PUBLIC_SUPABASE_ANON_KEY=$NEXT_PUBLIC_SUPABASE_ANON_KEY \
    NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL \
    NEXT_PUBLIC_STORAGE_ORIGIN=$NEXT_PUBLIC_STORAGE_ORIGIN \
    NEXT_TELEMETRY_DISABLED=1

RUN pnpm build

FROM node:22-slim
RUN useradd --create-home web
WORKDIR /app
ENV NODE_ENV=production HOSTNAME=0.0.0.0 PORT=3000

COPY --from=build --chown=web:web /app/.next/standalone ./
COPY --from=build --chown=web:web /app/.next/static ./.next/static
COPY --from=build --chown=web:web /app/public ./public

USER web
EXPOSE 3000
CMD ["node", "server.js"]
