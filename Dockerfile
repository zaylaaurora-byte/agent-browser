# syntax=docker/dockerfile:1

# ─── Stage 1: Base deps (Playwright + Python) ────────────────────────────────
FROM python:3.11-slim AS base-deps

RUN apt-get update && apt-get install -y --no-install-recommends \
    wget curl gnupg ca-certificates \
    libglib2.0-0 libnss3 libnspr4 libdbus-1-3 libatk1.0-0 \
    libatk-bridge2.0-0 libcups2 libdrm2 libxkbcommon0 libxcomposite1 \
    libxdamage1 libxfixes3 libxrandr2 libgbm1 libasound2 libpango-1.0-0 \
    libcairo2 libatspi3.0 libxshmfence1 \
    && rm -rf /var/lib/apt/lists/*

# Install Playwright browsers (cached layer)
RUN pip install --no-cache-dir playwright==1.48.0 \
    && playwright install chromium --with-deps 2>/dev/null || playwright install chromium

# ─── Stage 2: Backend ───────────────────────────────────────────────────────
FROM python:3.11-slim AS backend

WORKDIR /app

COPY --from=base-deps /root/.cache/ms-playwright /root/.cache/ms-playwright

RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 libnss3 libnspr4 libdbus-1-3 libatk1.0-0 \
    libatk-bridge2.0-0 libcups2 libdrm2 libxkbcommon0 libxcomposite1 \
    libxdamage1 libxfixes3 libxrandr2 libgbm1 libasound2 libpango-1.0-0 \
    libcairo2 libatspi3.0 libxshmfence1 \
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

# ─── Stage 4: Runner (production) ───────────────────────────────────────────
FROM ubuntu:24.04 AS runner

ENV DEBIAN_FRONTEND=noninteractive \
    NODE_ENV=production \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    nodejs nginx \
    && rm -rf /var/lib/apt/lists/* \
    && ln -s /usr/bin/node /usr/local/bin/node

WORKDIR /app

# Copy built Next.js frontend from stage 3
COPY --from=frontend-build /app/.next ./.next
COPY --from=frontend-build /app/public ./public
COPY --from=frontend-build /app/package.json ./

# Copy Playwright browsers from base-deps
COPY --from=base-deps /root/.cache/ms-playwright /root/.cache/ms-playwright

# Copy Python deps from backend stage
COPY --from=backend /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=backend /usr/local/bin /usr/local/bin

# Copy backend source
COPY --from=backend /app /app

# Write nginx config
RUN echo 'daemon off;' > /etc/nginx/nginx.conf
RUN cat > /etc/nginx/sites-available/default << 'NGINXCONF'
server {
    listen 80;
    server_name _;

    client_max_body_size 100M;
    gzip on;

    # Next.js static files
    location /_next/ {
        alias /app/.next/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    location / {
        root /app;
        try_files $uri $uri/ /index.html;
    }

    # Backend API proxy
    location /api/ {
        proxy_pass http://127.0.0.1:8001;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # WebSocket proxy
    location /ws/ {
        proxy_pass http://127.0.0.1:8001;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_read_timeout 86400;
    }
}
NGINXCONF

EXPOSE 80

ENV MINIMAX_API_KEY="" \
    OPENAI_API_KEY="" \
    AI_MODEL="MiniMax-M2.7"

CMD ["nginx"]
