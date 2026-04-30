# Agent Browser — AI-Powered Browser Automation

## Overview

Agent Browser is an autonomous web automation tool powered by AI. It uses Playwright for browser control and LLMs (MiniMax-M2.7) for decision-making. Watch the agent navigate, fill forms, extract data, and complete tasks in real-time with live reasoning.

## Architecture

```
┌─────────────────────┐     WebSocket      ┌──────────────────────┐
│   Next.js Frontend   │ ◄──────────────► │   FastAPI Backend     │
│   (port 3002)        │                    │   (port 8001)        │
│                      │                    │                      │
│  • Parallax Hero     │   HTTP /api/*      │  • WebSocket handler │
│  • Browser Viewport  │ ──────────────►   │  • BrowserAgent      │
│  • Activity Feed     │                    │  • Playwright        │
│  • Settings Page     │                    │  • MiniMax LLM       │
└─────────────────────┘                    └──────────────────────┘
```

## Tech Stack

- **Frontend**: Next.js 16, React 19, Tailwind CSS 4, Framer Motion, Lucide Icons, shadcn/ui
- **Backend**: FastAPI, Playwright, MiniMax-M2.7 (via OpenAI-compatible API)
- **Communication**: WebSocket for real-time streaming, HTTP for REST endpoints

## Project Structure

```
agent-browser/
├── src/
│   ├── app/
│   │   ├── globals.css          # Dark theme, glassmorphism, animations
│   │   ├── layout.tsx           # Root layout with navbar
│   │   ├── page.tsx             # Dashboard (hero + agent browser)
│   │   └── settings/
│   │       └── page.tsx         # Settings page (model, agent, connection)
│   ├── components/
│   │   ├── navbar.tsx           # Global navigation bar
│   │   ├── hero-section.tsx     # Parallax hero with animated orbs
│   │   ├── agent-browser.tsx    # Main dashboard: task input, viewport, activity
│   │   └── ui/                  # shadcn/ui primitives
│   └── lib/
│       └── utils.ts
├── backend/
│   ├── main.py                  # FastAPI app, REST + WebSocket endpoints
│   ├── browser_agent.py         # Core agent: Playwright + LLM decision loop
│   ├── .env                     # API keys (MINIMAX_API_KEY)
│   ├── requirements.txt
│   └── venv/
├── next.config.ts               # Proxy /api/* to backend:8001
├── package.json
└── README.md
```

## Getting Started

### Prerequisites
- Node.js 18+
- Python 3.11+
- MiniMax API key

### Backend
```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
playwright install chromium

# Set your API key
echo "MINIMAX_API_KEY=your-key-here" > .env

# Start
python3 -m uvicorn main:app --host 0.0.0.0 --port 8001
```

### Frontend
```bash
npm install
npm run dev -- --port 3002
```

Open http://localhost:3002

## Features

### 3 Agent Modes
- **Fast**: Quick execution, minimal delays, no stealth
- **Stealth**: Human-like typing, random delays, anti-detection patterns
- **Deep**: Full page analysis with forms, interactables, and detailed observations

### Live Agent Viewer
- Real-time browser screenshots streamed via WebSocket
- Screenshot filmstrip for step-by-step review
- AI reasoning panel shows the model's thinking process
- Activity feed with expandable reasoning, observations, and error details

### Settings Page
- Model provider selection (MiniMax, OpenAI, Anthropic, Ollama)
- Model name and API key configuration
- Max steps and default mode
- Headless mode toggle
- Backend URL configuration
- All settings persisted to localStorage

## WebSocket Protocol

### Send (client → server)
```json
{ "url": "https://example.com", "task": "Describe the page", "mode": "deep" }
```

### Receive (server → client)
Each step is streamed as JSON:
```json
{
  "step": 1,
  "action": "navigate",
  "argument": "https://example.com",
  "status": "completed",
  "screenshot": "base64...",
  "ai_reasoning": "The user wants me to...",
  "observation": "Page has 3 forms, 2 buttons...",
  "duration_ms": 1234,
  "model": "MiniMax-M2.7",
  "url": "https://example.com"
}
```

Step statuses: `thinking`, `completed`, `failed`, `retrying`
Terminal action: `done` with `answer` field containing the result.

## Anti-Hang Patches

The Playwright integration has timeout protection on all actions:
- `click()`: `wait_for_load_state="commit"`, 5s timeout
- `submit()`: 15s timeout with commit-based wait
- `check()`: `no_wait_after=True`, 5s timeout
- `fill()`: `no_wait_after=True`
- `_take_screenshot()`: 10s timeout
- Per-step: 30s overall timeout via `asyncio.wait_for()`

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/health` | GET | Health check |
| `/api/execute` | POST | Execute task (returns full result) |
| `/ws/agent` | WebSocket | Real-time streaming execution |
