# One image for the whole app: React is built in stage 1, FastAPI serves it plus the API in stage 2.
# One origin means cookies and CORS behave the same locally and in production.

FROM node:22-alpine AS frontend
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY backend/requirements.txt ./
RUN pip install -r requirements.txt
COPY backend/ ./
COPY --from=frontend /build/dist ./static
RUN useradd --system --uid 10001 pantry && chown -R pantry /app
USER pantry
# CD passes the image tag so /health reports which build is serving (deploy.sh waits for it).
ARG APP_VERSION=dev
ENV STATIC_DIR=/app/static PORT=8000 APP_VERSION=${APP_VERSION}
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=3s --start-period=20s --retries=5 \
  CMD python -c "import os,urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\",\"8000\")}/health')"
# `sh -c` so Render's $PORT is honoured; exec keeps uvicorn as PID 1 for clean shutdown.
CMD ["sh", "-c", "exec uvicorn app.main:app_factory --factory --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*'"]
