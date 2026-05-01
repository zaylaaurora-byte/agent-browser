---
name: agent-browser
description: AI-powered headless browser automation via Playwright. Give it a URL + task, it navigates, interacts, and reasons through steps live.
triggers:
  - run a task in the browser
  - automate web interactions
  - scrape with AI reasoning
  - test a flow end-to-end
---

# Agent Browser Skill

## Quick Start

```bash
cd ~/Projects/agent-browser/backend
source venv/bin/activate
uvicorn main:app --reload --port 8001
```

Then open `http://localhost:3000` (frontend).

## Architecture

```
Frontend (Next.js :3000)  ←→  WebSocket  ←→  Backend (FastAPI :8001)
                                                      ↓
                                              Playwright Browser
```

- **Frontend**: Next.js, WebSocket client, screenshot viewer, activity feed
- **Backend**: FastAPI + Playwright, `browser_agent.py` = core agent logic
- **Key file**: `backend/browser_agent.py` — the `BrowserAgent` class

## Running Tasks

1. Open the frontend
2. Enter a URL + task description
3. Select mode: **fast** (12 steps), **standard** (20), **deep** (30)
4. Click Execute — watch steps stream live

## Key Files

| File | Purpose |
|------|---------|
| `backend/browser_agent.py` | Core agent: action parsing, AI calls, Playwright execution |
| `backend/main.py` | FastAPI app: WebSocket endpoint, REST API |
| `backend/prompts/system.md` | System prompt — edit here to change agent behavior |
| `backend/prompts/action_rules.md` | Action format rules |
| `frontend/src/components/agent/` | Split components (index, task-input, browser-viewport, etc.) |

## Agent Loop

```
AI decides action → parse action → execute with Playwright
  → get page state → feed to AI → repeat until done or step limit
```

### Available Actions

`navigate`, `click`, `type`, `press`, `scroll`, `screenshot`, `wait`, `done`

### Modes & Limits

| Mode | Max Steps | Max Total Actions |
|------|-----------|-------------------|
| fast | 12 | 48 |
| standard | 20 | 80 |
| deep | 30 | 120 |

## Development

### Test the backend imports
```bash
cd ~/Projects/agent-browser/backend
source venv/bin/activate
python3 -c "import browser_agent; print('OK')"
```

### Restart uvicorn after .env changes
The backend reads `MINIMAX_API_KEY` at startup — restart required for changes.

### Run a specific test manually
```bash
cd ~/Projects/agent-browser/backend
source venv/bin/activate
python3 -c "
import asyncio
from browser_agent import BrowserAgent

async def test():
    agent = BrowserAgent()
    await agent.execute('https://example.com', 'Tell me what this page is about', 'fast')
    print(agent.conversation_history[-1]['answer'])

asyncio.run(test())
"
```

## Important Gotchas

1. **MiniMax thinking blocks** — MiniMax-M2.7 emits `<think thinker>...</think thinker>` in responses. `browser_agent.py` strips these via `_clean_ai_response()` and `_clean_answer()`. If adding a new model, check for this.

2. **Page load strategy** — Use `domcontentloaded` + 1s sleep, NOT `networkidle`. Heavy pages (Wikipedia analytics pings) hang on `networkidle` indefinitely.

3. **Popup auto-dismiss** — Cookie banners/modals are auto-dismissed before every action step. The dismissal runs in the same step as the action. Multiple sequential popups are handled by looping the dismiss check.

4. **Login wall detection** — If the agent hits auth/login URLs or detects email+password fields, it reports the wall and stops early.

5. **Step limit is a safety** — Hard cap at 4x the step limit prevents runaway loops. If you need more steps, increase the mode limit in `browser_agent.py`.

6. **Backend URL** — Frontend reads from `settings.backendUrl` in localStorage. Default if unset: `ws://localhost:8001/ws/agent`.

## Adding New Actions

1. Add to `VALID_ACTIONS` tuple in `browser_agent.py`
2. Add handler method `async def _do_your_action(self, arg):`
3. Call it from `_execute_action()` match block
4. Add description to system prompt in `prompts/system.md`

## System Prompt Location

`backend/prompts/system.md` — edit here, not in the Python file. The prompt controls how the AI reasons, what actions it can take, and answer quality rules.
