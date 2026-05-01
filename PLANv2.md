# Agent Browser — PLANv2 (QA Run — May 1, 2026)

## Where We Are

**Frontend** — Rebuilt with Next.js 16 + component split (Browser/Thinking/Activity tabs, live WebSocket streaming, dark glassmorphism). Component split done: `agent/index.tsx` as orchestrator, `task-input.tsx`, `browser-viewport.tsx`, `thinking-panel.tsx`, `activity-feed.tsx`, `result-panel.tsx`, `lightbox.tsx`, `keyboard-shortcuts.tsx`, `settings-modal.tsx`.

**Backend** — FastAPI + Playwright, anti-hang patches applied (wait_for_load_state="commit", no_wait_after, 30s per-step timeout). Stealth has UA rotation + 29 cookie selectors. Phase 3.4 stealth enhancements (canvas, AudioContext, WebGL spoofing, bezier mouse, random scroll).

**WebSocket delivery** — Streams JSON per step with: step#, action, status (thinking/completed/failed/retrying), screenshot (base64), ai_reasoning, observation, duration_ms, model name, URL.

---

## Bugs Found During QA Run (May 1, 2026)

### 🔴 BUG-01: Execute Button Click Doesn't Trigger WebSocket
- **Severity:** High
- **Symptom:** Clicking the Execute button (ref=e10) does not establish a WebSocket connection. The `onExecute` prop calls `run()` in the parent, but clicking the button in Playwright doesn't fire the React `onClick` handler.
- **Root cause:** React's synthetic event system may not fully fire from Playwright's `click()` in certain DOM contexts. The `run()` function IS correctly wired (Ctrl+Enter keyboard shortcut works).
- **Workaround:** Use keyboard shortcut `Ctrl+Enter` (Cmd+Enter on Mac) to trigger execution instead of clicking the button.
- **Fix needed:** Investigate why React `onClick` doesn't fire from Playwright's `click()`. Possible causes: event delegation, button being re-rendered between locate and click, or React strict mode double-invoking. Fix: either (a) ensure button is in viewport and not occluded before clicking, (b) use `page.evaluate(() => document.querySelector('[class*="btn-execute"]').click())` as fallback, or (c) expose `run()` via `window` and call it directly.

### 🔴 BUG-02: CAPTCHA Interstitial Blocking Sites
- **Severity:** Critical (blocks the agent entirely)
- **Symptom:** Yelp, Domino's, and similar sites show a `captcha-delivery.com` iframe interstitial before the real page loads. The agent has no iframe detection/dismissal for this pattern.
- **Root cause:** No iframe detection in Phase 3.2. The agent sees the iframe but doesn't know to dismiss it. The `_get_page_content()` enhanced page state (Apr 2026) reports `iframe_count` but the agent's system prompt doesn't instruct it to handle iframe blockers proactively.
- **Affected sites:** Yelp, Domino's, any site using captcha-delivery.com or similar CAPTCHA-as-a-service
- **Fix needed:** Add iframe dismissal logic to Phase 3.2: (a) detect `captcha-delivery.com`, `hcaptcha.com`, `recaptcha.net` in iframe src, (b) auto-close those iframes, (c) add a `PAGE_WARNINGS` note in the AI prompt about detected CAPTCHAs/iframes, (d) implement retry logic when CAPTCHA detected

### 🟡 BUG-03: Step Numbers Duplicated in Activity Feed
- **Severity:** Low
- **Symptom:** Steps appear twice with same number (e.g., "#5" appears for both the thinking phase and the completed phase). The frontend increments step# per thinking AND per completed, not once per action.
- **Root cause:** `index.tsx` adds `d.timestamp = Date.now()` on every `onmessage`, then adds the step. But the agent sends a "thinking" status message AND a "completed" status message for each action. Both get step numbers, and both appear in the feed.
- **Fix needed:** In `index.tsx` `onmessage`, replace the thinking/completed split with a single step per action: the thinking step is replaced by the completed step (same step#), not added separately. Use `step` number from the backend as the canonical identifier.

### 🟡 BUG-04: Execute Button Shows `Execute` Text Even During Run
- **Severity:** Low
- **Symptom:** The button text shows `Execute` instead of `Stop · N` even while the agent is running (after Ctrl+Enter triggered it). The progress strip and step count ARE updating, so state is running.
- **Root cause:** Race condition in React state update timing, or the button is rendering before state fully transitions.
- **Fix needed:** Ensure `isRunning` state transitions synchronously before `onExecute` returns.

### 🟡 BUG-05: Yelp SPA — Agent Stuck in Wait Loop
- **Severity:** Medium (known limitation, but needs better handling)
- **Symptom:** When the agent navigates to Yelp, it detects an iframe CAPTCHA interstitial and gets stuck in `wait(3)/wait(5)/screenshot` loops trying to wait it out. It doesn't make progress but keeps spending steps.
- **Root cause:** The agent doesn't have a "give up after N attempts" heuristic for CAPTCHA wait loops. It keeps retrying forever.
- **Fix needed:** Add max retry count per action type (e.g., max 3 screenshot attempts before flagging CAPTCHA and stopping with a clear error message).

### 🟡 BUG-06: Live Activity Panel Sits Below Fold on Small Viewports
- **Severity:** Low
- **Symptom:** The live activity panel (right column, Activity tab) is below the fold on certain viewport sizes. User must scroll to see it.
- **Root cause:** The 3-panel layout (viewport + thinking + activity) is desktop-first. Mobile shows tabs but the active tab content may still be below the fold.
- **Fix needed:** Ensure the mobile tab bar sticks at the bottom or that switching to Activity tab scrolls to the panel. Also improve the "Launch Agent" button (top of page) to scroll down to the agent section on click.
- **Fix applied (May 1, 2026):** Added `pb-24 xl:pb-0` to main grid (accounts for fixed tab bar height), added `flex-1` to ActivityFeed to expand on mobile, `scrollToActivity` already scrolls feed into view on tab switch, `scrollToAgent` exposed via window for Launch Agent button.
- **Status:** ✅ Fixed
---

## Fixes Applied During This QA Run

- **BUG-01 Workaround confirmed:** `Ctrl+Enter` keyboard shortcut successfully triggers WebSocket connection and execution
- **BUG-03 identified:** Step duplication visible in activity feed — fix needed in frontend state management

---

## Updated Roadmap (incorporating bug fixes)

### Phase 1.x — Critical Bug Fixes (Do First)

**1.x.1 Fix Execute Button Click** — Investigate Playwright `click()` on React button. Use `document.evaluate().click()` fallback or expose `window.runAgent()` in index.tsx.

**1.x.2 CAPTCHA/iframe Auto-Dismiss** — Add iframe detection and auto-dismiss to Phase 3.2 page state. Detect captcha-delivery.com, hcaptcha, recaptcha iframes. Close them before proceeding. Add `PAGE_WARNINGS: CAPTCHA detected` to AI prompt when present.

**1.x.3 Step Number Deduplication** — Fix frontend to show one step per action, not duplicate for thinking/completed phases.

### Phase 2.x — UX Polish

**2.x.1 Activity Panel Above Fold** — Ensure Activity tab scrolls into view when active. Make "Launch Agent" button scroll to agent section.

**2.x.2 Execution Feedback** — Make Execute button transition to Stop state immediately on click (optimistic UI).

### Phase 3.x — Agent Intelligence (Updates)

**3.x.1 CAPTCHA Heuristic** — After 3 consecutive `wait()` actions with no page state change, flag as "CAPTCHA blocked" and stop with clear message.

**3.x.2 Smarter SPA Navigation** — For Google Maps, Yelp, and similar SPAs: detect if `document.readyState` is `complete` but page content is still empty/iframe. Add explicit wait for specific DOM elements instead of blind wait() loops.

---

## Test Results Summary (May 1, 2026)

| Test | Target | Mode | Result | Notes |
|------|--------|------|--------|-------|
| Frontend loads | localhost:3002 | — | ✅ Pass | All panels render, dark theme OK |
| Execute (button click) | Yelp Bristol | Deep | ❌ Fail | BUG-01: button click doesn't trigger WS |
| Execute (Ctrl+Enter) | Yelp Bristol | Deep | ✅ Pass | WS connects, streams 26 steps |
| Live activity panel | — | — | ✅ Pass | Steps streaming with timestamps + reasoning |
| CAPTCHA handling | Yelp | Deep | ❌ Fail | BUG-02: captcha-delivery iframe not dismissed |
| Step numbering | — | — | 🟡 Partial | BUG-03: duplicate step numbers |
| Button state during run | — | — | 🟡 Partial | BUG-04: text delay |
| Target: Domino's | dominos.com | Fast | ❌ Fail | Antibot/CAPTCHA wall (known limitation) |
| Target: Google Maps | Maps search | Fast | 🟡 Partial | SPA loop (known limitation) |
| Target: httpbin pizza form | httpbin.org | Fast | ✅ Pass | Fully functional (baseline sanity check) |

---

## Recommended Execution Order

1. **Fix BUG-01 (Execute button)** — makes the product usable without keyboard workaround
2. **Fix BUG-02 (CAPTCHA/iframe)** — unblocks most commercial sites
3. **Fix BUG-03 (step deduplication)** — clean UX improvement
4. Then continue with Phase 1 original roadmap (settings→backend pipeline)
5. Then Phase 4 (run history DB — enables QA with real data)
6. Then Phase 3.x (agent intelligence improvements from this test)
