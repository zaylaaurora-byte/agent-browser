# syntax=docker/dockerfile:1

# ─── Stage 1: Base deps (Playwright + Python) ────────────────────────────────
FROM python:3.11-slim AS base-deps

RUN apt-get update && apt-get install -y --no-install-recommends \
    wget curl gnupg ca-certificates \
    libglib2.0-0 libnss3 libnspr4 libdbus-1-3 libatk1.0-0 \
    libatk-bridge2.0-0 libcups2 libdrm2 libxkbcommon0 libxcomposite1 \
    libxdamage1 libxfixes3 libxrandr2 libgbm1 libasound2 libpango-1.0-0 \
    libcairo2 libatspi2.0 libxshmfence1 \
    && rm -rf /var/lib/apt/lists/*

# Install Playwright browsers (cached layer)
RUN pip install --no-cache-dir playwright==1.48.0 \
    && playwright install chromium --with-deps 2>/dev/null || playwright install chromium

# ─── Stage 2: Backend ───────────────────────────────────────────────────────
FROM python:3.12-slim AS backend

WORKDIR /app

COPY --from=base-deps /root/.cache/ms-playwright /root/.cache/ms-playwright

RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 libnss3 libnspr4 libdbus-1-3 libatk1.0-0 \
    libatk-bridge2.0-0 libcups2 libdrm2 libxkbcommon0 libxcomposite1 \
    libxdamage1 libxfixes3 libxrandr2 libgbm1 libasound2 libpango-1.0-0 \
    libcairo2 libatspi2.0 libxshmfence1 \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .

ENV PYTHONUNBUFFERED=1

EXPOSE 8001

# Start backend only (run with: docker compose run --rm backend python -c "import main; print('ok')")
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]

# ─── Stage 3: Frontend build ─────────────────────────────────────────────────
FROM node:20-alpine AS frontend-build

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .

RUN npm run build

# ─── Stage 4: Runner (production) ────────────────────────────────────────────
FROM python:3.12-slim AS runner

ENV DEBIAN_FRONTEND=noninteractive \
    NODE_ENV=production \
    PYTHONUNBUFFERED=1

# Copy requirements.txt for pip install in runner
COPY backend/requirements.txt /tmp/requirements.txt

# NodeSource Node.js 20 + nginx + keyring deps (all on Debian Bookworm)
RUN apt-get update && apt-get install -y --no-install-recommends \
    nginx curl libdbus-1-3 \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir --break-system-packages -r /tmp/requirements.txt \
    && pip install --no-cache-dir --break-system-packages keyrings.alt \
    && ldconfig

WORKDIR /app

# Copy built Next.js frontend from stage 3
COPY --from=frontend-build /app/.next ./.next
COPY --from=frontend-build /app/public ./public
COPY --from=frontend-build /app/package.json ./
COPY --from=frontend-build /app/node_modules ./node_modules

# Copy Playwright browsers from base-deps
COPY --from=base-deps /root/.cache/ms-playwright /root/.cache/ms-playwright

# Copy backend source
COPY --from=backend /app /app

# Startup script: run backend (uvicorn) + frontend (next) + nginx concurrently
RUN printf '#!/bin/bash\ncd /app && python3 -m uvicorn main:app --host 0.0.0.0 --port 8001 &\ncd /app && ./node_modules/.bin/next start --port 3000 &\nexec nginx\n' > /start.sh && chmod +x /start.sh

# Write nginx config using printf
RUN printf '%s\n' \
    'daemon off;' \
    'events {' \
    '    worker_connections 1024;' \
    '}' \
    'http {' \
    '    include /etc/nginx/mime.types;' \
    '    default_type application/octet-stream;' \
    '    upstream backend {' \
    '        server 127.0.0.1:8001;' \
    '    }' \
    '    upstream frontend {' \
    '        server 127.0.0.1:3000;' \
    '    }' \
    '    server {' \
    '        listen 80;' \
    '        server_name _;' \
    '        client_max_body_size 100M;' \
    '        gzip on;' \
    '        location /_next/ {' \
    '            proxy_pass http://frontend;' \
    '            proxy_http_version 1.1;' \
    '            proxy_set_header Host $host;' \
    '            proxy_cache off;' \
    '        }' \
    '        location /api/ {' \
    '            proxy_pass http://backend;' \
    '            proxy_http_version 1.1;' \
    '            proxy_set_header Host $host;' \
    '            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;' \
    '            proxy_set_header X-Forwarded-Proto $scheme;' \
    '        }' \
    '        location /ws/ {' \
    '            proxy_pass http://backend;' \
    '            proxy_http_version 1.1;' \
    '            proxy_set_header Upgrade $http_upgrade;' \
    '            proxy_set_header Connection "upgrade";' \
    '            proxy_set_header Host $host;' \
    '            proxy_read_timeout 86400;' \
    '        }' \
    '        location / {' \
    '            proxy_pass http://frontend;' \
    '            proxy_http_version 1.1;' \
    '            proxy_set_header Host $host;' \
    '            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;' \
    '            proxy_set_header X-Forwarded-Proto $scheme;' \
    '        }' \
    '    }' \
    '}' > /etc/nginx/nginx.conf

EXPOSE 80

ENV MINIMAX_API_KEY="" \
    OPENAI_API_KEY="" \
    AI_MODEL="MiniMax-M2.7"

CMD ["/start.sh"]
