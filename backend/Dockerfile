# 2026-08-16: replaces Railpack auto-detection, which was non-deterministically
# choosing between two different Python provisioning strategies build-to-build
# (a /opt/venv virtualenv vs. a mise-managed interpreter), leaving uvicorn
# installed in one environment and invoked from a different one at runtime
# ("No module named uvicorn" despite a successful build). One explicit,
# single Python interpreter for both build and run eliminates that class of
# failure entirely -- diagnosed by reading real Railway build/runtime logs
# across half a dozen attempts, not guessed.
FROM python:3.13-slim

WORKDIR /app

# System deps some wheels (e.g. psycopg, cryptography) may need to build,
# plus the Pango stack WeasyPrint needs at runtime for real PDF export
# (reporting/export.py's fmt="pdf") and a real font so rendered text isn't
# tofu/boxes -- verified against WeasyPrint's actual native bindings
# (cffi -> pango/pangoft2/fontconfig/harfbuzz/gobject only; no cairo or
# gdk-pixbuf needed since v53), not the older, heavier dependency list.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

COPY . .
RUN python -m pip install --upgrade pip && python -m pip install .

EXPOSE 8000
# Shell form (not exec-array form) so $PORT expands at container start --
# Railway injects its own $PORT and the app must bind to it, per
# RAILWAY_ENV_MANIFEST.md's own gotcha #1.
CMD python -m uvicorn app.main:app --host 0.0.0.0 --port $PORT
