# One image serves the API and the built web app. Sized for Hugging Face Spaces' free
# Docker tier (port 7860, runs as uid 1000), but runs anywhere Docker does.

# ---------- Frontend build ----------
FROM oven/bun:1.4 AS frontend
WORKDIR /app/frontend
COPY frontend/package.json frontend/bun.lock ./
RUN bun install --frozen-lockfile
COPY frontend/ ./
# Public values only: these end up in browser JavaScript.
ARG VITE_CLERK_PUBLISHABLE_KEY=""
ARG VITE_MS_CLIENT_ID=""
ENV VITE_CLERK_PUBLISHABLE_KEY=$VITE_CLERK_PUBLISHABLE_KEY \
    VITE_MS_CLIENT_ID=$VITE_MS_CLIENT_ID
RUN bun run build

# ---------- Runtime ----------
FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    FINBO_STATIC_DIR=/app/static \
    FINBO_SAMPLES_DIR=/app/data/samples \
    FINBO_DB_PATH=/app/var/finbo.db \
    PORT=7860

RUN useradd --create-home --uid 1000 app
WORKDIR /app

COPY backend/pyproject.toml backend/
COPY backend/src backend/src
RUN pip install "./backend[postgres]"

COPY data/samples data/samples
COPY --from=frontend /app/frontend/dist static
RUN mkdir -p var && chown app:app var

USER app
EXPOSE 7860
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:' + __import__('os').environ['PORT'] + '/api/health')"
CMD ["sh", "-c", "uvicorn finbo.api:app --host 0.0.0.0 --port ${PORT}"]
