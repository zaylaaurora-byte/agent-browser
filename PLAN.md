# Agent Browser — Product Roadmap

## Where We Are

**Frontend** — Next.js 16 + Tailwind CSS 4 + Framer Motion. Dark glassmorphism UI with parallax hero. Main component is a single 569-line `agent-browser.tsx` (task input + browser viewport + thinking panel + activity feed). Settings page at `/settings`. All in `~/Projects/agent-browser/src/`.

**Backend** — FastAPI + Playwright. Single `browser_agent.py` handles all browser automation. Anti-hang patches confirmed solid (wait_for_load_state="commit", no_wait_after, 30s per-step timeout). Cookie banner auto-dismiss built-in. Stealth mode has 5 rotating user agents + 29 cookie selectors. System prompt hardcoded for action format.

**Backend-to-frontend delivery** — WebSocket at `ws://localhost:8001/ws/agent` streams each step as JSON with: step number, action, argument, status (thinking/completed/failed/retrying), screenshot (base64), ai_reasoning, observation, duration_ms, model name, URL.

**Settings** — Stored in localStorage only. Not persisted to backend. Provider selector (MiniMax/OpenAI/Anthropic/Ollama) exists in UI but API key isn't sent to backend on execute (browser_agent.py reads from its own `.env` via `os.getenv`).

---

## What Needs Updating

### Phase 1 — Infrastructure & Reliability

**1.1 Fix Settings → Backend Pipeline**
The settings UI lets you configure API key + model + provider, but these are never sent to the backend. `BrowserAgent` reads `os.getenv("MINIMAX_API_KEY")` from `.env` at import time — it's static for the lifetime of the uvicorn process. If you change the API key in settings, the backend keeps using the one from when it started.
- Add API key + model name to WebSocket message payload
- Update `main.py` websocket handler to pass them to `BrowserAgent.__init__`
- Add `self.api_key` and `self.model_name` fields to `BrowserAgent.__init__`
- Pass API key + model to `_call_ai()` so it uses what frontend sent
- This unblocks: changing model mid-session, multi-user API keys, API key in browser UI only

**1.2 Backend Health & Graceful Degradation**
If MiniMax API is down, the agent returns `ACTION: done(fallback message)` — a very dumb fallback. We should:
- Catch API errors explicitly and surface them as a step with `status: "failed"` + error message
- Implement a simple retry with exponential backoff on API calls (3 attempts, 1s → 2s → 4s)
- Show API errors in the UI activity feed so the user knows what failed
- Add a `/api/config` GET endpoint that returns current backend config (model, max_steps, etc.)

**1.3 Session Management**
Currently each WebSocket connection creates a brand-new `BrowserAgent()` instance. There's no:
- Session persistence — can't pause/resume a run
- Session history — can't revisit a past run
- Multiple concurrent sessions — each WS connection is isolated
- Later phases depend on this, so we scaffold it now:
  - `session_id` generated on connect, stored in a `sessions` dict
  - Store: `{id, created_at, task, url, mode, status, steps[], final_answer, started_at}`
  - Expose `/api/sessions` (GET list) and `/api/sessions/{id}` (GET one)
  - Sessions expire after 24h automatically

---

### Phase 2 — Frontend UX Polish

**2.1 Split agent-browser.tsx**
At 569 lines this is unwieldy. Split into:
```
src/components/agent/
  ├── index.tsx              # Main orchestrator, WebSocket logic, state
  ├── task-input.tsx         # URL bar + task textarea + mode selector + quick launches
  ├── browser-viewport.tsx   # Chrome bar + screenshot display + filmstrip
  ├── thinking-panel.tsx     # Live reasoning feed
  ├── activity-feed.tsx      # Step cards with expand/collapse
  ├── result-panel.tsx       # Final answer display
  └── step-card.tsx         # Individual step card (action, observation, reasoning toggle)
```
Keep `src/components/agent-browser.tsx` as a barrel re-export for zero-breaking changes.

**2.2 Empty States & Skeleton Loaders**
Current empty states are flat text ("No activity yet", "Execute a task to see the browser"). Replace with:
- Animated skeleton loaders for the activity feed during first 2 seconds of a run
- A branded empty state illustration for when no task has been run yet
- A "session expired" empty state if the user navigates back after a long gap
- Use framer-motion stagger for entrance animations on skeleton items

**2.3 Screenshot Viewer — Full Lightbox**
Currently screenshots are only visible as tiny 80px thumbnails in step cards and 16:9 in the main viewport. Add:
- Click on main viewport screenshot → full lightbox modal with zoom (wheel to zoom, drag to pan)
- Click on filmstrip thumbnail → swaps main viewport without disrupting stream
- Screenshot comparison mode: side-by-side two screenshots from different steps
- Download individual screenshot as PNG
- All stored as base64 in memory, no server round-trip needed

**2.4 Step Timeline / Filmstrip View**
Right now the activity feed is a vertical list. Add an alternative view:
- Horizontal timeline at the top of the activity panel showing step thumbnails as a filmstrip
- Clicking a step jumps the main viewport to that screenshot
- Color-coded dots: green=completed, red=failed, violet=thinking, gray=pending
- Scrubbing the timeline shows animated transitions between screenshots

**2.5 Keyboard Shortcuts**
- `Cmd/Ctrl + Enter` — Execute task
- `Escape` — Stop running task
- `Space` — Pause/resume stream (when implemented)
- `1-9` — Jump to step N in the filmstrip
- `R` — Replay last task
- Show a `?` help overlay listing all shortcuts

**2.6 Improved Settings Page**
Current settings are localStorage only. Add:
- "Test Connection" button that hits `/api/health` and shows latency
- "Test Model" button that sends a tiny test prompt and shows the response + latency
- Provider-specific fields: for Ollama show "Base URL" field instead of API key; for OpenAI show model dropdown (gpt-4o, gpt-4o-mini, etc.)
- Import/export settings as JSON
- Settings validation: warn if API key looks wrong (e.g. too short for OpenAI)
- Dark/light theme toggle in settings (currently forced dark)

---

### Phase 3 — Agent Intelligence

**3.1 Smarter Action System**
Current system is single-action-per-turn. The AI decides "type in this field" and that's one action. This is slow and expensive for multi-field forms. Improve:
- **Action batching**: allow AI to return multiple actions in one turn, executed sequentially with human delays between them (e.g., "type name, type email, check checkbox, click submit" = 4 actions in 4 seconds)
- **New actions to support**:
  - `select_option(selector, value)` — for `<select>` dropdowns
  - `hover(selector)` — for hover-dependent UI (dropdowns, tooltips)
  - `dblclick(selector)` — for double-click actions
  - `switch_to_frame(selector)` — for iframes
  - `switch_to_tab(index)` — for tab management
  - `get_text(selector)` — extract text content for verification
  - `evaluate(js)` — run arbitrary JS and return result (power user feature)
- **Retry intelligence**: when a step fails, don't just retry the same action — analyze the error and try an alternative approach. E.g., if click fails, try a different selector or `evaluate()` to click via JS.

**3.2 Better Page State Understanding**
Current `_get_page_content()` extracts form fields, interactives, and text. But it's noisy and misses:
- Dynamic content loaded after DOM (SPAs, React apps) — add a wait for network idle
- Shadow DOM elements
- ARIA live regions (for dynamic updates)
- Image alt text and SVG content descriptions
- Cookie consent state (already dismisses but doesn't report it)
- `<select>` options with full text + value
- iframe content
- Improve `_get_page_content()` to return structured data with: page state (loaded/spa/dynamic), detected cookie banners (with which selector was used), detected CAPTCHAs (with screenshot证据), detected iframes count, full select options array

**3.3 Multi-Agent Support**
Right now the system is single-agent. To support more complex workflows:
- Add an `AgentPool` class that manages multiple concurrent browser contexts
- Expose a `/api/agents` endpoint that lets you spawn named agents
- Support orchestrating multiple agents: "open 3 job boards simultaneously and extract listings"
- Each agent gets its own browser context, they communicate through the backend
- WebSocket message format gets a new `agent_id` field

**3.4 Stealth Mode Enhancement**
Stealth currently does: random UA rotation, basic JS injection, cookie dismiss. Add:
- Canvas fingerprint randomization (spoof WebGL renderer)
- AudioContext fingerprint spoofing
- `navigator.hardwareConcurrency` spoofing
- Random mouse movement paths (bezier curves, not just `move_to`)
- Random scroll behavior (not just fixed `300-700px`)
- Proxy support: if a proxy URL is in settings, route all browser traffic through it
- Respect `robots.txt` opt-out (add as a config option)
- Detect and report: is Cloudflare challenge page showing? Is there a CAPTCHA? Did any stealth feature get detected?

---

### Phase 4 — Persistence & History

**4.1 Run History Database**
Currently runs are ephemeral — they disappear when the browser tab closes. Add:
- SQLite database at `backend/runs.db` (simple, zero-dependency, persists across restarts)
- Schema: `runs(id, session_id, created_at, task, url, mode, status, final_answer, steps_count, duration_ms, error)`
- Steps stored in a separate `steps` table: `steps(id, run_id, step_num, action, argument, status, screenshot_path, ai_reasoning, observation, duration_ms)`
- Screenshots saved to `backend/screenshots/{run_id}/{step_num}.png` (not base64 in DB — saves space, enables compression)
- WebSocket handler saves each step to DB as it streams (fire-and-forget, don't block on it)
- Add `/api/runs` (list last 50, paginated), `/api/runs/{id}` (full detail), `/api/runs/{id}/screenshot/{step}` (serve screenshot file)
- Add a "History" page in the frontend at `/history` showing past runs with search/filter

**4.2 Session Resume**
If a run was interrupted (network cut, page crash, user stopped), allow resuming:
- Store the full `conversation_history` + `page.url` at the point of interruption
- New `/api/runs/{id}/resume` endpoint returns: `{url, task, conversation_history, step_number}`
- When user clicks "Resume", frontend reconnects WebSocket with a `resume_from` flag
- Backend skips navigation, restores conversation history, and continues from where it stopped

**4.3 Export & Sharing**
- Export a run as JSON (all step data, no screenshots) or PDF (readable report with screenshots embedded)
- Share a run via a short link: `/run/{short_id}` that replays the run in read-only mode
- "Duplicate run" — re-run the same task+URL with one click

---

### Phase 5 — Advanced Features

**5.1 Task Templates & Workflows**
- Save any executed task as a reusable template (name + description + task text + URL pattern)
- Templates stored in localStorage + optionally synced to backend
- Workflows: chain multiple templates together with conditions
  - E.g., "Login → Search Jobs → Extract Listings → Export CSV"
  - Condition nodes: "if X appears, do Y else do Z"
  - Each step can have a different agent mode
- Visual workflow builder at `/workflows` (drag-and-drop nodes, no-code)

**5.2 Data Extraction Mode**
Add a specialized mode for structured data extraction:
- Instead of executing arbitrary actions, the agent crawls a page and extracts to a schema
- User defines schema: `{jobs: [{title, company, location, salary, url}]}` or `{products: [...]}`
- Agent returns JSON matching the schema
- Display extracted data in a clean table/card view in the UI
- Export to CSV/JSON/Google Sheets
- Use cases: job board scraping, product price monitoring, real estate listings, news articles

**5.3 Scheduling**
- Backend already has Celery in requirements (unused). Wire it up:
  - `POST /api/schedule` — schedule a task to run at a time or on a cron expression
  - `GET /api/scheduled` — list scheduled runs
  - `DELETE /api/scheduled/{id}` — cancel
- Scheduled runs execute via Celery worker, results stored in DB
- Notifications: when a scheduled run completes, fire a browser Notification API ping (if user grants permission) + show in UI
- Use cases: daily job alerts, weekly price checks, nightly data collection

**5.4 Browserbase & Cloud Browser Support**
Currently only runs locally via Playwright. Add cloud browser options:
- Browserbase integration: `BROWSERBASE_API_KEY` env var + `use_browserbase=True` setting
- If enabled, sessions run on Browserbase remote browsers instead of local Playwright
- Benefits: residential proxies, stealth is handled server-side, persistent sessions
- Also support: Sauce Labs, LambdaTest, or any Playwright CDP endpoint

---

## Phase Summary

| Phase | Focus | Key Deliverables |
|-------|-------|-----------------|
| **1** | Infrastructure | Settings→backend pipeline, API retry/backoff, session DB scaffold |
| **2** | UX Polish | Component split, skeleton loaders, lightbox, timeline view, keyboard shortcuts |
| **3** | Agent Intelligence | Action batching, multi-agent, enhanced stealth, richer page state |
| **4** | Persistence | SQLite run history, screenshots on disk, history page, session resume |
| **5** | Advanced | Task templates/workflows, data extraction, scheduling, cloud browsers |

---

## Recommended Execution Order

1. **Do Phase 1 first** — settings being disconnected from backend is a critical bug that makes the product hard to use
2. **Then Phase 4** — run history enables you to iterate on everything else with real data
3. **Then Phase 2** — UX polish is visible quickly and validates the product feel
4. **Then Phase 3** — agent intelligence is where most of the hard AI work lives
5. **Then Phase 5** — advanced features layer on top once the core loop is solid

---

## Tech Debt & Known Issues

- [ ] `next.config.ts` proxy rewrites `/api` to `localhost:8001` — works locally but breaks if backend is on a different host in production. Needs a proper base URL config.
- [ ] `.env` in backend holds `MINIMAX_API_KEY` but it's never reloaded. Restarting uvicorn is required after changing the key.
- [ ] `agent-browser.tsx` has hardcoded `ws://localhost:8001/ws/agent` — needs to read from settings `backendUrl`
- [ ] No TypeScript strict mode — add `strict: true` to `tsconfig.json` and fix all `any` types
- [ ] No unit tests anywhere. Minimum: test `_parse_action()` regex, `_call_ai()` with mock, `_execute_action()` with Playwright mock.
- [ ] Celery is in `requirements.txt` but unused — either remove it or wire up scheduling
- [ ] `browser_agent.py` SYSTEM_PROMPT is hardcoded at the top of the file. Should be in `prompts/` directory as `.md` files for easy editing.
- [ ] No rate limiting on `/api/execute` — a user can spam it and burn through API credits
- [ ] Screenshots are base64 strings in WebSocket frames — very large payloads, can cause browser memory issues on long runs (50+ steps)
- [ ] `main.py` has a dead `celery` import reference (if Celery is configured later)
- [ ] No `package-lock.json` or `yarn.lock` checked in — dependency versions are floating

## Bugs Found During Phase 1

- [x] **Fixed** Settings API key + model name were never sent from frontend to backend — `BrowserAgent` always used `.env` values at startup. Fixed by passing `api_key` and `model_name` via WebSocket message payload and storing on the agent instance.
- [x] **Fixed** Single AI retry with no backoff — API failures would immediately fall back to dumb fallback. Fixed with 3-attempt exponential backoff (1s → 2s).
- [x] **Fixed** API errors silently swallowed — fallback AI was returned but UI had no indication the API had failed. Fixed by tagging `model_name="error"` on exhausted retries and yielding a `failed` step that terminates the run.
- [x] **Fixed** No session persistence — runs were completely ephemeral. Fixed with in-memory `_sessions` dict, session lifecycle tracking (running/completed/failed/stopped), and REST endpoints (`/api/sessions`, `/api/sessions/{id}`).
- [x] **Fixed** WebSocket `agent.cleanup()` called without null-check on disconnect — would throw if agent was never initialized. Fixed with `if agent: await agent.cleanup()` guard.
- [ ] **Known** Sessions are in-memory only — if uvicorn restarts, all session history is lost. Phase 4 will move to SQLite for persistence.
- [ ] **Known** `agent-browser.tsx` had hardcoded `ws://localhost:8001/ws/agent` — Fixed in Phase 2, frontend now reads `backendUrl` from settings.

## Phase 2 Done ✅

**2.1 — Component split** ✅
- `agent-browser.tsx` (580 lines) split into 8 focused components in `src/components/agent/`:
  - `index.tsx` — main orchestrator + WebSocket logic + state
  - `task-input.tsx` — URL bar, mode selector, execute button, quick launches
  - `browser-viewport.tsx` — Chrome bar, screenshot display, filmstrip thumbnails
  - `thinking-panel.tsx` — live reasoning feed
  - `activity-feed.tsx` — step cards with expand/collapse reasoning
  - `result-panel.tsx` — final answer display
  - `lightbox.tsx` — full screenshot lightbox with zoom/pan/download
  - `keyboard-shortcuts.tsx` — `?` help overlay
  - `settings-modal.tsx` — settings modal with provider/model/API key/backend URL
  - `types.ts` — shared types, constants, icons, quick sites
- `agent-browser.tsx` is now a barrel re-export (zero-breaking change)
- TypeScript: zero errors

**2.2 — Empty states** ✅
- Activity feed empty state now shows "Press `?` for shortcuts" hint
- Branded empty states for browser viewport and thinking panel

**2.4 — Screenshot lightbox** ✅
- Click main screenshot → full lightbox modal
- Scroll to zoom (0.5x–5x), drag to pan, keyboard +/-/0
- Download as PNG, close with Escape or click outside

**2.5 — Keyboard shortcuts** ✅
- `Cmd/Ctrl+Enter` → execute task
- `Escape` → stop running task
- `r` → replay last task (restores URL + task + mode from localStorage)
- `?` → show shortcuts overlay
- Lightbox: `+`/`-` zoom, `0` reset, `Esc` close

**2.6 — Hardcoded WS URL fixed** ✅
- Frontend reads `backendUrl` from settings (localStorage) on every execute
- Settings modal lets you configure the backend WebSocket URL
- Provider selector (MiniMax / OpenAI / Anthropic / Ollama) with model dropdown
- "Test Connection" button hits `GET /api/health` and shows status
- API key + model name sent on every execute (per Phase 1 fix, now also using configurable URL
