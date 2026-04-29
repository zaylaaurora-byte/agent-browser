# Agent Browser

AI-powered browser automation with stealth anti-detection.

## Quick Start

```bash
# Frontend
cd frontend && npm install && npm run dev

# Backend
cd backend
python -m venv venv && source venv/activate
pip install -r requirements.txt
playwright install
python main.py
```

## Environment

```env
MINIMAX_API_KEY=your_key
REDIS_URL=redis://localhost:6379/0
```

## API

- `POST /api/execute` - Execute browser task
- `WebSocket /ws/agent` - Real-time streaming

## Tech Stack

- Next.js + shadcn/ui (dark)
- FastAPI + Playwright
- MiniMax AI
- Redis + Celery
- Stealth anti-detection