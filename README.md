# Agent Browser — AI-Powered Browser Automation

> Autonomous web automation with stealth anti-detection. 22/22 board tasks passing (May 2026).

## Overview

Agent Browser is an autonomous web automation tool powered by AI. It uses Playwright for browser control and LLMs (MiniMax-M2.7, OpenAI, Anthropic, Ollama) for decision-making. Watch the agent navigate, fill forms, extract data, and complete tasks in real-time with live reasoning.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│  Next.js Frontend (port 3002)                                            │
│  ┌──────────────┐ ┌──────────────────┐ ┌─────────────────────────────┐ │
│  │ Parallax Hero│ │ Live Agent Viewer│ │ Supervisor Dashboard       │ │
│  │ + Settings   │ │ (screenshot film- │ │ (pause/resume/undo/log)     │ │
│  │              │ │ strip, reasoning) │ │                             │ │
│  └──────────────┘ └──────────────────┘ └─────────────────────────────┘ │
│         │                  ▲                        ▲                    │
│         │ HTTP rewrites    │ WebSocket              │ REST               │
└─────────┼──────────────────┼────────────────────────┼────────────────────┘
          │                  │                        │
          ▼                  │                        │
┌─────────────────────────────────────────────────────────────────────────┐
│  FastAPI Backend (port 8001)                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐ │
│  │ BrowserAgent — AI decision loop (ai_router, domain_memory,         │ │
│  │ action_history, session_manager, credential_vault, captcha_solver) │ │
│  └─────────────────────────────────────────────────────────────────────┘ │
│                              │                                            │
│                              ▼                                            │
│  ┌─────────────────────────────────────────────────────────────────────┐ │
│  │ Playwright — stealth browser (tls_fingerprint, proxy_manager,        │ │
│  │ visual_diff, workflow_recorder, MCP server (20 tools))             │ │
│  └─────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘
```

## Tech Stack

- **Frontend**: Next.js 15, React 19, Tailwind CSS 4, Framer Motion, Lucide Icons, shadcn/ui
- **Backend**: FastAPI, Playwright, ai_router (MiniMax-M2.7, OpenAI, Anthropic, Ollama)
- **AI**: Multi-model routing via `ai_router.py` — MiniMax with thinking disabled, OpenAI, Anthropic, Ollama local
- **Communication**: WebSocket for real-time streaming, HTTP for REST endpoints
- **Persistence**: SQLite (workflows, domain memory), JSON files (sessions), OS keychain + Fernet (credentials)

## Quick Start

```bash
cd ~/Projects/agent-browser
cp .env.example .env   # add MINIMAX_API_KEY or OPENAI_API_KEY

# Start both backend + frontend
./start.sh
# Backend: http://localhost:8001 (FastAPI docs at /docs)
# Frontend: http://localhost:3002
```

Or manually:

```bash
# Backend (port 8001 — NOT 8000, that's Hermes)
cd backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
playwright install chromium
python3 -m uvicorn main:app --host 0.0.0.0 --port 8001

# Frontend (port 3002)
cd ../ && npm install && npm run dev -- --port 3002
```

## Features

### Agent Modes
| Mode | Max Steps | Description |
|------|-----------|-------------|
| `fast` | 15 | Quick execution, minimal delays |
| `deep` | 25 | Full page analysis, forms, interactables |

### Phase 1 — Stealth Hardening
- Residential proxy rotation (Bright Data, ScraperAPI, generic)
- TLS/JA3/JA4 fingerprint spoofing (Chrome/Firefox/Safari profiles)
- WebRTC IP leak blocking
- GPU randomization (16-entry pool)
- Viewport randomization with ±20px jitter
- Canvas, AudioContext, WebGL spoofing

### Phase 2 — Session Persistence
Named sessions save cookies, localStorage, viewport, UA, proxy to `~/.agent-browser/sessions/{name}.json` (mode `0o600`). Sessions survive backend restarts.

### Phase 3 — Action Batching + Enhanced Page State
- **Action Batching**: AI returns multiple actions per response, executed sequentially
- **New actions**: `select_option`, `hover`, `dblclick`, `switch_to_tab`, `get_text`, `evaluate`
- **Retry Intelligence**: alternate selectors → JS fallback before giving up
- **Enhanced Page State**: SPA detection, CAPTCHA detection, cookie banner, iframe count, select dropdown options, shadow DOM count, ARIA live regions
- **Human-like Motion**: cubic bezier mouse paths, fractional viewport scroll

### Phase 4 — Action History + Undo
Captures browser state snapshot before every undoable action. Undo restores cookies, localStorage, URL, scroll position.

### Phase 5 — Credential Vault
Encrypted credential storage with domain scoping and TOTP 2FA support. Passwords NEVER go to the AI — they flow directly from vault to page form via blind fill.

### Phase 6 — MCP Server (20 tools)
stdio transport for Claude Code/Desktop, HTTP for Hermes integration:

| Tool | Description |
|------|-------------|
| `browser_navigate` | Navigate to URL |
| `browser_click` | Click by CSS selector or `@eN` ref |
| `browser_type` | Human-like typing |
| `browser_press` | Keyboard key |
| `browser_snapshot` | Accessibility tree with ref IDs |
| `browser_screenshot` | Base64 JPEG screenshot |
| `browser_extract_content` | Plain text or structured JSON |
| `browser_scroll` | Human-like scroll |
| `browser_back` | Browser back navigation |
| `browser_wait_for` | Poll page for text (up to 30s) |
| `browser_list_tabs` | List all open tabs |
| `browser_switch_tab` | Switch tab by index |
| `browser_session_save` | Persist browser state |
| `browser_session_load` | Restore named session |
| `browser_get_page_info` | URL, title, engine, loading state |
| `browser_undo` | Best-effort browser-history undo |
| `workflow_save` | Save workflow to SQLite |
| `workflow_replay` | Replay saved workflow |
| `workflow_export` | Export as JSON |
| `workflow_import` | Import from JSON |
| `workflow_list` | List saved workflows |
| `dom_diff` | Visual diff between screenshots |
| `dom_classify` | Classify page elements (content/modal/nav/ad) |

### Supervisor Dashboard (`/supervisor`)
Real-time agent oversight: pause/resume, undo, session save/load, live thinking display, action timeline, runtime stats.

## API Endpoints

### REST
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | Health check |
| POST | `/api/execute` | Execute a task (REST, one-shot) |
| GET | `/api/persistent-sessions` | List all saved sessions |
| POST | `/api/persistent-sessions/{name}/save` | Save current browser state |
| POST | `/api/persistent-sessions/{name}/load` | Load a named session |
| DELETE | `/api/persistent-sessions/{name}` | Delete a session |
| POST | `/api/vault/credential` | Add a credential |
| GET | `/api/vault/domains` | List domains with stored creds |
| POST | `/api/vault/fill/{domain}` | Blind fill: returns username + password + TOTP |
| GET | `/api/history?limit=N` | Get action history |
| POST | `/api/history/undo` | Undo last action |
| POST | `/api/supervisor/pause` | Pause agent after current step |
| POST | `/api/supervisor/resume` | Resume agent |
| GET | `/api/supervisor/status` | Agent status |
| POST | `/api/sessions/{id}/stop` | Stop a session |
| DELETE | `/api/sessions/{id}` | Delete a session |
| GET | `/api/metrics` | Session metrics |

### WebSocket
```
ws://localhost:8001/ws/agent
```
Send: `{"url": "https://example.com", "task": "Describe the page", "mode": "deep"}`
Receive: streamed JSON steps with `thinking`, `observation`, `screenshot_url`, `duration_ms`, `model`

## Backend Files

| File | Purpose |
|------|---------|
| `browser_agent.py` | Core agent: Playwright + AI decision loop |
| `ai_router.py` | Multi-model router: MiniMax, OpenAI, Anthropic, Ollama |
| `domain_memory.py` | Learns site structure, auto-injects context |
| `session_manager.py` | Named session persistence |
| `credential_vault.py` | Encrypted credentials with TOTP 2FA |
| `captcha_solver.py` | 2Captcha, Anti-Captcha, CapSolver integration |
| `action_history.py` | Action history + undo system |
| `proxy_manager.py` | Residential proxy rotation |
| `tls_fingerprint.py` | JA3/JA4 TLS fingerprint spoofing |
| `visual_diff.py` | PIL/numpy screenshot diffing |
| `workflow_recorder.py` | SQLite workflow recorder |
| `mcp_server.py` | MCP server (20 tools, stdio + HTTP) |
| `main.py` | FastAPI app: REST + WebSocket + lifespan |

## Verified (May 2026)

```bash
cd backend && source venv/bin/activate
python3 -c "from browser_agent import BrowserAgent; print('browser_agent OK')"
python3 -c "import ai_router; print('ai_router OK')"
python3 -c "import domain_memory; print('domain_memory OK')"
python3 -c "import captcha_solver; print('captcha_solver OK')"
python3 -c "import visual_diff; print('visual_diff OK')"
python3 -c "import workflow_recorder; print('workflow_recorder OK')"
```

**22/22 board tasks passing** — see `.board/prd.json`.

## Known Limitations

- Commercial antibot sites (Indeed, Expedia, Workable) will block headless Chrome. Use httpbin.org forms for testing, or add a stealth proxy layer (Bright Data, ScraperAPI).
- Backend requires DBus/keyring for OS keychain credential vault. In environments without DBus (e.g., Docker), it falls back to file-based master key at `~/.agent-browser/vault/.masterkey` (mode `0o600`).
- `deep` mode is limited to 25 steps. If tasks seem to run forever, check the mode enum mapping in `stream_execute()`.

## GitHub

https://github.com/zaylaaurora-byte/agent-browser
