#!/usr/bin/env bash
set -e

echo "🌐 Starting Agent Browser..."

# Check if backend venv exists
if [ ! -d "backend/venv" ]; then
    echo "📦 Setting up backend..."
    cd backend
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    playwright install chromium
    cd ..
fi

# Start backend
echo "⚡ Starting backend (FastAPI on :8001)..."
cd backend
source venv/bin/activate
python3 -m uvicorn main:app --host 0.0.0.0 --port 8001 &
BACKEND_PID=$!
cd ..

# Wait for backend
sleep 3

# Start frontend
echo "⚡ Starting frontend (Next.js on :3002)..."
npm run dev -- --port 3002 &
FRONTEND_PID=$!

echo ""
echo "✅ Agent Browser is running!"
echo "   Frontend: http://localhost:3002"
echo "   Backend:  http://localhost:8001"
echo "   API Docs: http://localhost:8001/docs"
echo ""
echo "Press Ctrl+C to stop"

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT TERM
wait
