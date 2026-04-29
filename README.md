# 🌐 Agent Browser

AI-powered browser automation with stealth anti-detection. Point it at any URL, give it a task, and it navigates, clicks, reads, and returns answers autonomously.

## Features

- 🤖 **AI Agent** — Uses MiniMax / OpenAI to decide what to click, type, and read
- 🥷 **Stealth** — Anti-detection: randomized UA, WebGL spoofing, human-like delays, plugin faking
- 📸 **Screenshots** — Live screenshot capture after every action
- 🔌 **REST + WebSocket** — HTTP for simple tasks, WebSocket for real-time streaming
- 🌙 **Dark UI** — Clean dark mode interface built with Next.js + shadcn/ui

## Quick Start

```bash
# Clone
git clone https://github.com/zaylaaurora-byte/agent-browser.git
cd agent-browser

# Setup env
cp .env.example .env
# Edit .env with your API key

# Install frontend deps
npm install

# One command to start both backend + frontend
./start.sh
```

Or start manually:

```bash
# Backend
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
playwright install chromium
python3 -m uvicorn main:app --host 0.0.0.0 --port 8001

# Frontend (separate terminal)
npm run dev
```

Open **http://localhost:3000**

## Architecture

```
Frontend (Next.js :3000)
    ↕ REST / WebSocket
Backend (FastAPI :8001)
    ↕
Browser Agent (Playwright + Stealth)
    ↕
AI Model (MiniMax / OpenAI)
```

## API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/api/health` | GET | Health check |
| `/api/execute` | POST | Execute a browser task |
| `/ws/agent` | WebSocket | Stream execution step-by-step |
| `/docs` | GET | FastAPI interactive docs |

### POST /api/execute

```json
{
  "url": "https://example.com",
  "task": "What text is visible on this page?",
  "mode": "fast"
}
```

Response:
```json
{
  "answer": "The page title is \"Example Domain\"...",
  "steps_executed": 2,
  "steps_failed": 0,
  "screenshot": "<base64 png>",
  "history": [...]
}
```

## Configuration

| Env Variable | Default | Description |
|---|---|---|
| `MINIMAX_API_KEY` | — | MiniMax API key (or set OPENAI_API_KEY) |
| `MINIMAX_BASE_URL` | `https://api.minimax.chat/v1` | API base URL |
| `AI_MODEL` | `MiniMax-M2.5` | Model to use |

## Tech Stack

- **Frontend:** Next.js 15, TypeScript, Tailwind CSS, shadcn/ui
- **Backend:** FastAPI, Playwright, OpenAI Python SDK
- **AI:** MiniMax-M2.5 (or any OpenAI-compatible model)
- **Stealth:** Anti-webdriver, UA rotation, WebGL spoofing, human delays

## License

MIT
