# ⚡ AGENT BROWSER — WORLD-CLASS UPGRADE PLAN
**Audited:** May 8, 2026 | **Model:** MiniMax-M2.7 | **Status:** Active

---

## WHAT THIS IS

A fully audited, prioritised improvement plan to make agent-browser genuinely world-class — a browser agent that can do **anything** on the web with real evidence outputs, production-grade reliability, and operator-grade UX.

---

## 📊 FULL AUDIT FINDINGS

### 🔴 CRITICAL — Do First

| # | Finding | File | Impact |
|---|---------|------|--------|
| C-01 | 200+ bare `except Exception:` and `except:` blocks silently swallow errors | browser_agent.py, mcp_server.py, antibot_escalation.py | Failures are invisible, debugging impossible |
| C-02 | `iframe_click`, `iframe_type`, `iframe_hover` actions have no handlers — AI gets silent fail | browser_agent.py | Nested content (ads, CAPTCHAs, auth flows) breaks without feedback |
| C-03 | `upload` action missing — only works via `form_fill`, can't do standalone file uploads | browser_agent.py | Job applications requiring CVS/resume upload broken |
| C-04 | `handle_dialog` missing — alerts/confirms hang the agent indefinitely | browser_agent.py | Booking/payment flows that trigger native dialogs break |
| C-05 | `wait_for_navigation` missing — click-based navigations don't wait for load | browser_agent.py | Regular link navigations cause timing failures |
| C-06 | `switch_to_frame` missing — nested iframes can't be targeted | browser_agent.py | Complex SPAs with iframe auth (OAuth callbacks, embedded content) broken |

---

### 🟡 HIGH PRIORITY — Do Second

| # | Finding | File | Impact |
|---|---------|------|--------|
| H-01 | 8 npm packages outdated (next 16.2.4→16.2.6, react 19.2.4→19.2.6, typescript 5.9.3→6.0.3, eslint 9.39.4→10.3.0) | package.json | Security/correctness risk, new features blocked |
| H-02 | Site overrides cover 14 sites — missing Kayak, Hotels.com, Vrbo, Hostelworld, Agoda, Skyscanner | site_overrides.py | Travel benchmark incomplete |
| H-03 | Frontend has no theme toggle, session replay, metrics dashboard, task templates, or multi-task queue | src/app/supervisor/page.tsx | UX far from "world-class" |
| H-04 | MCP execute_task reuses singleton agent — state bleed risk across concurrent requests | mcp_server.py | Multi-user/parallel use cases fail |
| H-05 | `book` action not implemented — can search but can't complete booking/payment | browser_agent.py | Cannot fulfil the core holiday requirement |
| H-06 | No frontend test suite — 0 Jest unit tests, 0 Playwright E2E tests | __tests__/ | Every change risks regression |

---

### 🟢 MEDIUM/LOW — Do Third

| # | Finding | File | Impact |
|---|---------|------|--------|
| L-01 | Dead code in browser_agent.py:1359-1366 (duplicate `_dismiss_captcha_iframe` definition) | browser_agent.py | Maintenance confusion |
| L-02 | PLANv2.md BUG markers still reference non-existent section labels | PLANv2.md | Stale documentation |
| L-03 | No token usage tracking in supervisor (estimate cost per task) | src/app/supervisor/page.tsx | Users can't assess cost efficiency |
| L-04 | Frontend has no dark/light mode toggle | src/app/supervisor/page.tsx | User preference gap |
| L-05 | `escalate_unblocker_proxy` and `escalate_firefox` don't re-navigate after restart | antibot_escalation.py | Escalation paths land on about:blank instead of target URL |
| L-06 | No regression test coverage for exception handling paths | backend/ | Silent breakages in error paths |

---

## 🗺️ 7-PHASE EXECUTION PLAN

### PHASE 1 — Frontend Operator Experience *(T731)*
**Goal:** Make the UI feel genuinely world-class — something an operator would trust with real money.

**Deliverables:**
- [ ] Dark / Light / System theme toggle with persistence (localStorage)
- [ ] Session history panel — timeline replay of past agent runs (steps + screenshots)
- [ ] Performance metrics — live steps/sec, avg thinking time, failure rate by domain
- [ ] Task templates — preset buttons for holiday search, pizza order, job apply, signup, social
- [ ] Multi-task queue — add N tasks, execute sequentially, show aggregate report
- [ ] Real-time token usage estimate (prompt + completion tokens via response headers)

**Verification:** Run `npm run build` ✓ → supervisor renders with new features → screenshot to Telegram

---

### PHASE 2 — Missing Action Handlers *(T732)*
**Goal:** Zero silent failures — every AI-generated action either works or gives a clear error.

**Deliverables:**
- [ ] `book` action — Stripe test card flow (4242424242424242), fill payment fields, click Pay/Book, capture confirmation reference
- [ ] `upload` action — standalone `el.set_input_files(file_path)` from arg `selector, file_path`
- [ ] `handle_dialog` action — `page.on("dialog")` handler set in `_init_browser()`, dialog dismissed/accepted via action arg
- [ ] `wait_for_navigation` action — `page.wait_for_navigation(wait_until="domcontentloaded", timeout=ms)`
- [ ] `switch_to_frame` action — `page.frame(name_or_selector)` switch
- [ ] `iframe_click`, `iframe_type`, `iframe_hover` — find iframe → content doc → query → perform action
- [ ] Unknown action guard — `else: result["error"] = f"Unknown action: {action}"` instead of silent fall-through

**Verification:** `python3 -m pytest backend/test_action_handlers.py` all pass

---

### PHASE 3 — Site Override Expansion *(T733)*
**Goal:** Holiday benchmark must cover the sites real travellers use.

**Deliverables:**
- [ ] Kayak override — `datasobek-Box-kayakcom` search, `td[class*="md"]` calendar, `button[data-testid="search-button"]`
- [ ] Hotels.com override — `q-destination`, `q-check-in`, `q-check-out`, `q-rooms`, `button[type="submit"]`
- [ ] Vrbo override — `[data-stid="destination-form"] input`, `div[data-stid="date-range-picker"]`, `button[data-stid="search-btn"]`
- [ ] Agoda override — `searchDestination`, calendar, guest selector
- [ ] Skyscanner override — `div[data-testid="origin"]`/`destination`, `div[data-testid="calendar"]`
- [ ] Hostelworld override — `destination-input`, date picker, guest count

**Each needs:** extra_headers (Accept-Language, Currency), post_nav_js (antibot JS), post_nav_delay (1.5-2s), form_selectors, date_picker_selectors, requires_proxy flag

**Verification:** Run 20-task benchmark → booking.com + new sites → screenshots evidence

---

### PHASE 4 — Error Hygiene *(T734)*
**Goal:** Every failure is visible, categorised, and recoverable — not silently swallowed.

**Deliverables:**
- [ ] Audit all 200+ bare `except:` blocks in browser_agent.py, mcp_server.py, antibot_escalation.py
- [ ] Replace with structured logging: `logger.warning("context", extra={"error": str(e), "retryable": True/False})`
- [ ] Categorise errors: RETRYABLE (timeout, network, CAPTCHA) vs FATAL (auth, payment, unknown action)
- [ ] Retry-loop for RETRYABLE errors (3 attempts with exponential backoff)
- [ ] Regression test per critical failure path (simulate error, verify clean recovery)

**Verification:** Run full test suite — 0 silent failures in logs

---

### PHASE 5 — Dependency Refresh *(T735)*
**Goal:** Stay current, stay secure, stay fast.

**Deliverables:**
- [ ] Upgrade npm batch 1: `next 16.2.4→16.2.6`, `react 19.2.4→19.2.6` — git checkpoint → install → test → commit
- [ ] Upgrade npm batch 2: `typescript 5.9.3→6.0.3`, `eslint 9.39.4→10.3.0`, `shadcn 4.6.0→4.7.0` — git checkpoint → install → test → commit
- [ ] Upgrade npm batch 3: `@types/node 20.19.39→25.6.2`, `eslint-config-next 16.2.4→16.2.6` — git checkpoint → install → test → commit
- [ ] Pip audit: check for security patches in current pinned versions
- [ ] Final: `npm run build` ✓ + full pytest suite ✓

**Verification:** `npm run build` succeeds, pytest passes, no regression in live smoke test

---

### PHASE 6 — Testing *(T736)*
**Goal:** Every significant change has a regression test.

**Deliverables:**
- [ ] Jest unit tests for: `index.tsx` (execute flow), `supervisor/page.tsx` (WS state machine), `activity-feed.tsx` (step rendering/dedup)
- [ ] Pytest integration tests for: MCP execute_task singleton isolation (fresh agent per call), step schema contract, transport parity
- [ ] Playwright E2E smoke: navigate to `/`, fill task, click Execute, verify steps stream, verify result

**Verification:** `npm test` ✓ + `pytest` ✓ + E2E smoke ✓

---

### PHASE 7 — Live Holiday Benchmark *(T737)*
**Goal:** Real evidence — pre-payment totals from 8+ sites, normalised output, screenshots at every stage.

**Deliverables:**
- [ ] Run agent against: Booking.com, TUI, Jet2, LoveHolidays, OnTheBeach, Kayak, Hotels.com, Vrbo
- [ ] Task: search Sept 8, 7 nights, 3 adults + 3 children (<17), budget < £4,000, beach + all-inclusive + water park
- [ ] Capture: screenshots at search → results → detail → checkout stages
- [ ] Output normalised JSON: `{site, url, occupancy, board, total_checkout, screenshots[], confidence, strict_vs_partial}`
- [ ] 15+ qualified options with strict/partial labels + reason
- [ ] Report: pass/fail per site, top failures, fix plan

**Verification:** JSON artifact + screenshot pack delivered to `/home/zayla/Projects/agent-browser/screenshots_live_test/`

---

## 🎯 SUCCESS CRITERIA

After all 7 phases complete:

| Metric | Target |
|--------|--------|
| Holiday benchmark pass rate | ≥85% across 8+ sites |
| Silent error rate | 0 (every failure is logged) |
| Frontend test coverage | >80% of components tested |
| Action handler coverage | 100% — no unknown-action silent fails |
| Site override count | 20+ sites covered |
| Build health | `npm run build` ✓ always |
| Test health | `pytest` + `npm test` ✓ always |
| UX quality | Dark/light mode, session replay, metrics, templates all functional |

---

## 🚦 EXECUTION ORDER

```
T731 → T732 → T733 → T734 → T735 → T736 → T737
Phase1   Phase2  Phase3  Phase4  Phase5  Phase6  Phase7
```

Each phase: verify → commit → push before starting next.  
Live benchmark (Phase 7) runs only after Phases 1-6 pass their gates.