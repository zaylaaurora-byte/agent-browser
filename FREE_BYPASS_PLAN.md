# Free Antibot Bypass — Implementation Plan
**Goal:** Make agent-browser work on commercial antibot sites without paying for Bright Data/Oxylabs

---

## Research Findings

### What Works (Free)

| Method | Stealth Level | JS Challenge Bypass | Free? | Status |
|--------|--------------|---------------------|--------|--------|
| **nodriver** | ⭐⭐⭐⭐⭐ | Yes (patches Chrome internals) | ✅ | Best option — install |
| **SeleniumBase Stealthy Playwright** | ⭐⭐⭐⭐ | Yes (via UC connect_over_cdp) | ❌ | Requires license |
| **FlareSolverr** | ⭐⭐⭐⭐ | Yes (full browser) | ✅ Docker only | Docker perms denied |
| **undetected-chromedriver** | ⭐⭐⭐ | Partial (patched ChromeDriver) | ✅ | Installed but chromedriver version mismatch |
| **Camoufox** | ⭐⭐⭐ | Partial (Firefox TLS differs) | ✅ | Already integrated |
| **Webshare free proxies** | ⭐ | None | ✅ | Datacenter IPs only, easy to detect |
| **Free proxy lists** | ⭐ | None | ✅ | Unreliable, mostly blocked |

### What Doesn't Work
- **Residential proxy trials without credit card** — all require card
- **FlareSolverr without Docker** — only runs in Docker; no perms on this machine
- **undetected-chromedriver** — chromedriver 148 ≠ Chrome 147 (version mismatch)

### Key Insight: nodriver
`nodriver` (by ultrafunkamsterdam, same author as undetected-chromedriver) is the **successor** — async, no chromedriver binary needed, patches Chrome DevTools Protocol to remove detection signals, and is actively maintained. It passes Cloudflare JavaScript challenges by mimicking real Chrome behavior at the CDP level.

---

## Architecture Decision: Hybrid Approach

**Selected strategy:** Add `nodriver` as a new **selectable browser engine** alongside existing tiers.

```
agent-browser currently supports:
  Tier 1: crawlee-jsdom     (no real browser, HTTP only)
  Tier 2: camoufox            (Firefox — different TLS fingerprint)  
  Tier 3: chromium            (standard Playwright Chrome)

Add:
  Tier 4: nodriver            (stealth Chrome via CDP, async, no chromedriver binary)
```

**How it works:**
1. nodriver launches Chrome with stealth patches applied at runtime
2. Exposes a Chrome DevTools Protocol websocket URL
3. Playwright connects via `connect_over_cdp(ws_url)` to use nodriver's stealth browser
4. Full Playwright API (clicks, types, navigation) + nodriver's stealth = best of both worlds

**Integration pattern:**
```python
# Option A: Pure nodriver (async, full control)
browser = await nodriver.start(headless=True)
page = browser.main_tab
await page.goto('https://www.indeed.com')

# Option B: Hybrid (nodriver browser + Playwright API)
nodriver_browser = await nodriver.start()
ws_url = nodriver_browser.ws_url  # e.g., ws://127.0.0.1:9222/devtools/...
# Then connect Playwright: await pw.chromium.connect_over_cdp(ws_url)
```

**Why this works for antibot:**
- nodriver removes ~15 automation detection signals that Playwright doesn't
- Cloudflare challenges are solved by nodriver's stealth browser
- Playwright's stable API drives the browser after connection
- No API key or payment required

---

## Implementation Tasks

### T035: Install nodriver + verify basic operation
```
pip install nodriver
python3 -c "import nodriver; print('nodriver OK')"
```

### T036: Create nodriver_bridge.py
`backend/nodriver_bridge.py` — manages nodriver lifecycle:
- `start_browser(headless=True, proxy=None)` → returns (browser, ws_url)
- `stop_browser(browser)` → cleanup
- Applies proxy if provided
- Handles Chrome path detection

### T037: Add nodriver engine to browser_agent.py
In `_init_browser()`:
- Detect `BROWSER_ENGINE=nodriver`
- Launch via nodriver_bridge
- Connect Playwright over CDP to nodriver's websocket
- Set `self.page` to the connected Playwright page
- Apply existing TLS inject + stealth JS on top

### T038: Wire nodriver into site_overrides
For sites that need maximum stealth (Indeed, Domino's, Booking, etc.):
```python
"www.indeed.com": SiteOverride(
    ...
    tier_override="nodriver",  # Force nodriver for these sites
)
```

### T039: Free proxy integration (Webshare + proxy rotation)
- Webshare free: 10 datacenter IPs, 1GB/month, no credit card
- Sign up: webshare.io → free plan
- Add to proxy_manager: `webshare` provider
- Auto-rotate through free proxy list
- Fallback: use free public proxy lists (proxyscrape)

### T040: Clearance cookie solver (FlareSolverr-compatible)
- Since FlareSolverr needs Docker (denied), implement a **manual clearance flow**:
- When Cloudflare challenge detected → pause and inform user
- OR: Use a lightweight approach: have nodriver solve the challenge
- Then pass clearance cookies to Playwright via `context.add_cookies()`

### T041: Update site_overrides with working patterns
Improve header sets and cookie strategies based on testing.

### T042: Live test on Indeed.com
Navigate to Indeed with nodriver engine + Webshare proxy → verify no antibot block.

---

## Verification Criteria
1. `python3 -c "import nodriver; print('nodriver OK')"` → success
2. `BROWSER_ENGINE=nodriver` → browser launches without error
3. Indeed.com loads without Cloudflare challenge (or challenge solved)
4. Booking.com job search completes without block
5. All existing tests still pass (33/34 → 34/34)

---

## Time Estimate
- T035 (install): 2 min
- T036 (bridge): 15 min
- T037 (engine integration): 20 min
- T038 (site overrides wired): 10 min
- T039 (webshare free proxy): 15 min
- T040 (clearance solver): 15 min
- T041 (test patterns): ongoing
- T042 (live test): 10 min
**Total active work: ~90 minutes**
