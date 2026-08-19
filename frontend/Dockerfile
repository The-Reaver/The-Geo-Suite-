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
RUN npm run build

FROM node:20-slim
WORKDIR /app
ENV NODE_ENV=production
COPY --from=build /app ./

EXPOSE 3000
# Shell form so $PORT expands at container start -- Railway injects its own
# $PORT (RAILWAY_ENV_MANIFEST.md gotcha #1).
CMD npm run start -- --port ${PORT:-3000}
