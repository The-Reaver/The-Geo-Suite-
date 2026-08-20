# 2026-08-16: same reasoning as backend/Dockerfile -- replaces Railpack
# auto-detection, which was leaving the frontend service stuck on a stale
# cached build config (rootDirectory/builder settings not taking effect
# across several redeploy attempts) even after those settings were corrected
# via the API. One explicit, deterministic build removes that ambiguity.
FROM node:20-slim AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .

# Dockerfile builds on Railway are isolated from the host environment by
# design -- setting NEXT_PUBLIC_* as service variables does NOT expose them
# to this RUN step on its own. Next.js inlines process.env.NEXT_PUBLIC_*
# into the client bundle at build time, so without this ARG/ENV pair the
# build silently falls back to lib/supabaseClient.ts's placeholder host,
# which is exactly what shipped on this repo's first two "fixed" deploys
# (surfaced live as a browser "failed to fetch" on /login).
ARG NEXT_PUBLIC_SUPABASE_URL
ARG NEXT_PUBLIC_SUPABASE_ANON_KEY
ARG NEXT_PUBLIC_API_BASE_URL
ARG NEXT_PUBLIC_APP_NAME
ENV NEXT_PUBLIC_SUPABASE_URL=$NEXT_PUBLIC_SUPABASE_URL \
    NEXT_PUBLIC_SUPABASE_ANON_KEY=$NEXT_PUBLIC_SUPABASE_ANON_KEY \
    NEXT_PUBLIC_API_BASE_URL=$NEXT_PUBLIC_API_BASE_URL \
    NEXT_PUBLIC_APP_NAME=$NEXT_PUBLIC_APP_NAME

RUN npm run build

FROM node:20-slim
WORKDIR /app
ENV NODE_ENV=production
COPY --from=build /app ./

EXPOSE 3000
# Shell form so $PORT expands at container start -- Railway injects its own
# $PORT (RAILWAY_ENV_MANIFEST.md gotcha #1).
CMD npm run start -- --port ${PORT:-3000}
