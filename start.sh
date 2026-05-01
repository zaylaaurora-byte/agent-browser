#!/usr/bin/env bash
set -e

echo "🌐 Starting Agent Browser..."

# Detect LAN IP for phone/device access
LAN_IP=$(ip route get 1.1.1.1 2>/dev/null | awk '{for(i=1;i<=NF;i++) if ($i=="src") {print $(i+1); exit}}')
if [ -z "$LAN_IP" ]; then
  LAN_IP=$(hostname -I 2>/dev/null | awk '{print $1}')
fi
if [ -z "$LAN_IP" ]; then
  LAN_IP="<your-local-ip>"
fi

# ── Backend ───────────────────────────────────────────────
if [ ! -d "backend/venv" ]; then
  echo "📦 Setting up backend..."
  cd backend
  python3 -m venv venv
  source venv/bin/activate
  pip install -r requirements.txt
  playwright install chromium
  cd ..
fi

echo "⚡ Starting backend (FastAPI on :8001)..."
cd backend
source venv/bin/activate
python3 -m uvicorn main:app --host 0.0.0.0 --port 8001 &
BACKEND_PID=$!
cd ..

sleep 2

# ── Frontend ──────────────────────────────────────────────
echo "⚡ Starting frontend (Next.js on :3002)..."
npm run dev -- --port 3002 --hostname 0.0.0.0 &
FRONTEND_PID=$!

sleep 2

echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║           ✅  Agent Browser is running!              ║"
echo "║                                                      ║"
echo "║  Local:    http://localhost:3002                     ║"
printf "║  Network:  http://%-34s║\n" "${LAN_IP}:3002"
echo "║                                                      ║"
echo "║  Backend:  http://localhost:8001                     ║"
echo "║  API Docs: http://localhost:8001/docs                ║"
echo "║                                                      ║"
echo "║  📱 Phone: open the Network URL above               ║"
printf "║     Set backend to: ws://%-28s║\n" "${LAN_IP}:8001/ws/agent"
echo "╚══════════════════════════════════════════════════════╝"
echo ""
echo "Press Ctrl+C to stop"

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; echo ''; echo '👋 Stopped.'; exit" INT TERM
wait
