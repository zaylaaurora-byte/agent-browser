# Agent Browser — Strategic Improvement Plan (Phase 6+)
## Based on Competitive Analysis: Browser Use, Perplexity Comet, ChatGPT Atlas, Vessel, Skyvern, Mino

---

## What the Competition Has That We Don't

| Feature | Browser Use | Comet | Atlas | Vessel | Agent Browser |
|---|---|---|---|---|---|
| Multi-tab shared context | ❌ | ✅ | ✅ | ❌ | ❌ |
| Persistent memory (learns sites) | ❌ (requested) | ✅ | ✅ | ❌ | Session-only |
| Self-learning from failures | ❌ | ❌ | ❌ | ✅ (Mino does this) | Ralph (slow) |
| Workflow recording/replay | ❌ | ❌ | ❌ | ❌ | ❌ |
| Cloud deploy (Docker) | ✅ | ✅ | ✅ | ✅ | ❌ |
| Mobile-first UI | ❌ | ✅ | ❌ | ❌ | Broken (just fixed) |
| Purpose-built LLM for browser | ✅ (cloud) | ❌ | ❌ | ❌ | ❌ |
| Visual DOM diffing | ❌ | ❌ | ❌ | ❌ | ❌ |
| API-first architecture | ⚠️ | ⚠️ | ❌ | ⚠️ | WebSocket-only |
| Built-in benchmarks/smoke tests | ❌ | ❌ | ❌ | ❌ | Ralph (basic) |

**Browser Use cloud scores 78% vs 62% best open-source** — the gap is their purpose-built browser-automation LLM. That's a moat we can't easily copy, but we can out-execute on everything else.

---

## The 6 Major Improvements (Priority Order)

---

### 1. 🌊 Multi-Tab Sessions with Shared Context
**Why:** Browser Use is single-tab. Comet and Atlas both do multi-tab. Real tasks span multiple pages.

**What:**
- Agent spawns/closes tabs per task
- Shared `tab_manager` — all tabs accessible to all agents
- Cross-tab operations: "open results in new tab", "compare 3 pages"
- Tab state tracked in session store (SQLite)

**File changes:** `backend/agent/tab_manager.py` (new), extend `BrowserAgent`

**Complexity:** High. Reward: High.

---

### 2. 🧠 Persistent Domain Memory (Per-Site Heuristics)
**Why:** Browser Use GitHub issue — users explicitly asking for this. "Make it remember the right path and correct actions for next time." Mino does this with deterministic code; we do it with learned LLM prompts.

**What:**
- After each task, store DOM fingerprints + action sequences per domain
- On revisit: inject "site context" — what worked last time
- SQLite table: `domain_heuristics(domain, selector_map, action_sequence, success_rate, last_tested)`
- Auto-query this before starting a task on a known domain
- Phase 1: manual "learn this site" button. Phase 2: auto-learn after 3+ successes.

**File changes:** `backend/memory/heuristics.py` (new), `backend/db/schema.sql`

**Complexity:** Medium. Reward: High.

---

### 3. 🎬 Workflow Recorder (Macro Recording + Replay)
**Why:** No competitor does this well. Users want to record "do this sequence once" and replay it. Browser Use has no replay. Mino has deterministic replay but requires AI to figure it out each time.

**What:**
- In frontend: "Record" button — every action becomes a step in a workflow
- Each step: `{action: "click", selector: "#buy-btn", value: null}`
- Workflow saved to SQLite, downloadable as JSON
- Replay: feed workflow steps + current DOM state to LLM, ask "which step applies now"
- Export/import workflows, share via URL

**File changes:** `backend/workflows.py` (new), `frontend/components/workflow-recorder.tsx` (new)

**Complexity:** Medium. Reward: Very High (locks in users).

---

### 4. 🔍 Visual DOM Diffing Engine
**Why:** Agent does an action, waits for page change. Current approach: poll + snapshot. Brittle on slow SPAs. Browser Use has no visual diffing.

**What:**
- Screenshot before/after each action
- Compute pixel-level diff (PIL)
- If diff > threshold: page changed → proceed
- If diff < threshold: wait or retry
- Bonus: classify diff type (content change, modal opened, page navigated, ad loaded)
- Use for: smarter "wait for page to load", "detect if action succeeded"

**File changes:** `backend/agent/dom_diff.py` (new), extend agent loop

**Complexity:** Medium. Reward: Medium-High (reliability).

---

### 5. 🚢 Docker Cloud Deployment
**Why:** Users can't deploy agent-browser to a server. Browser Use has a cloud option. We want to be the self-hosted choice that's easier to deploy than Browser Use.

**What:**
- `Dockerfile` in root — frontend + backend in one image
- `docker-compose.yml` — single command up
- `Dockerfile.optimized` — multi-stage build, ~500MB vs ~2GB
- Environment variables: `OPENAI_API_KEY`, `MINIMAX_API_KEY`, `PORT`
- Health check: `curl localhost:8001/api/health`
- Push to Docker Hub with CI/CD

**File changes:** `Dockerfile`, `docker-compose.yml`, `.dockerignore`, `cloud.md`

**Complexity:** Low. Reward: High (distribution).

---

### 6. 📱 Mobile UI Pass (Actually Mobile-First)
**Why:** We just fixed the backend URL issue. But the UI is still desktop-first. Comet and Atlas both go mobile-first. Mobile-first AI browser = untapped market.

**What:**
- Responsive layout: stack panels vertically on mobile
- Swipe gestures for agent chat
- Pull-to-refresh session history
- Bottom nav bar (no sidebar on mobile)
- Settings accessible via sheet/drawer
- Touch: tap to select elements, pinch to zoom
- `mobile_layout.tsx` — conditional rendering based on viewport

**File changes:** `frontend/app/layout.tsx`, `frontend/components/mobile-nav.tsx` (new)

**Complexity:** Medium. Reward: Medium (differentiator).

---

## Architecture Changes Needed

### Backend REST API Expansion
Currently WebSocket-only. Add REST for workflow management, session history, heuristic queries.

```
GET  /api/workflows              — list saved workflows
POST /api/workflows              — create workflow
GET  /api/workflows/{id}        — get workflow
POST /api/workflows/{id}/execute — replay workflow
GET  /api/heuristics/{domain}   — get domain memory
POST /api/heuristics/{domain}   — update domain memory
GET  /api/tabs/{session_id}     — get tab state
POST /api/tabs                  — open new tab
DELETE /api/tabs/{tab_id}       — close tab
```

### Database Schema Extension
```sql
-- Workflows
CREATE TABLE workflows (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  steps JSON NOT NULL,  -- [{action, selector, value}, ...]
  created_at TEXT,
  last_used_at TEXT,
  use_count INTEGER DEFAULT 0
);

-- Domain Heuristics
CREATE TABLE domain_heuristics (
  domain TEXT PRIMARY KEY,
  selector_map JSON,      -- CSS selectors that worked
  action_sequence JSON,   -- Ordered actions
  success_rate REAL,       -- 0.0 - 1.0
  test_count INTEGER,
  last_tested_at TEXT
);

-- Tabs
CREATE TABLE tabs (
  tab_id TEXT PRIMARY KEY,
  session_id TEXT REFERENCES sessions(session_id),
  url TEXT,
  title TEXT,
  is_active BOOLEAN DEFAULT FALSE,
  created_at TEXT
);
```

---

## Implementation Phases

### Phase 6: Docker + REST API (Foundation)
- Docker setup
- REST endpoints for workflows + heuristics
- SQLite schema migration
→ **Deliverable:** `docker-compose up` deploys full stack

### Phase 7: Workflow Recorder
- Frontend recorder UI
- Workflow replay engine
- Workflow CRUD API
→ **Deliverable:** Record a task, replay it on new site variant

### Phase 8: Multi-Tab Sessions
- Tab manager
- Cross-tab context injection
- Tab-aware agent loop
→ **Deliverable:** "Open 5 product pages and summarize each"

### Phase 9: Domain Memory
- Heuristics capture after tasks
- Heuristics injection before tasks
- Manual "teach this site" UI
→ **Deliverable:** Agent learns that github.com login needs `#username` + `#password`

### Phase 10: Visual DOM Diffing
- Screenshot diffing engine
- Smart wait-for-change
- Diff classification
→ **Deliverable:** Reliable on slow SPAs (Booking, LinkedIn)

### Phase 11: Mobile UI Pass
- Responsive redesign
- Mobile nav + touch gestures
- Sheet/drawer settings
→ **Deliverable:** Works beautifully on iPhone/Android

---

## Competitive Moats We Can Build

1. **Ralph integration** — self-improving loop that's already running. Every failed task improves the heuristic store. No competitor has autonomous improvement.

2. **Workflow marketplace** — users share workflows. Built on top of the recorder. Browser Use has nothing close.

3. **Domain memory network** — if 1000 users teach the agent about LinkedIn, that knowledge compounds. Network effect on heuristics.

4. **Multi-agent + multi-tab combo** — Browser Use is single-agent single-tab. We can run Agent A on Tab 1 researching while Agent B on Tab 2 booking — in parallel.

---

## Quick Wins (This Week)

1. **Fix remaining frontend hot-reload** — port 3000 vs 3002 inconsistency
2. **Add `/api/health` to settings auto-detect** — already done in backend
3. **Dockerize** — highest impact per hour invested
4. **Workflow REST endpoints** — 4 endpoints, ~2 hours

---

## Risks

- **Scope creep** — 6 major improvements is a lot. Prioritize ruthlessly. Docker + REST first.
- **Playwright stability** — multi-tab will surface more Playwright edge cases
- **Memory bloat** — domain heuristics + session history + workflows = SQLite grows. Add cleanup cron.
- **LLM cost** — more context injection (heuristics, tab state) = more tokens per task. Monitor costs.
