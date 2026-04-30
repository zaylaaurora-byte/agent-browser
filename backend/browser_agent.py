"""Browser Agent - AI-controlled browser automation with stealth"""
import asyncio
import os
import json
import base64
import random
import time
import logging
from typing import AsyncGenerator, Optional
from datetime import datetime

from playwright.async_api import async_playwright, Browser, Page, BrowserContext

logger = logging.getLogger(__name__)

# Stealth browser arguments
STEALTH_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--disable-dev-shm-usage",
    "--no-sandbox",
    "--disable-setuid-sandbox",
    "--disable-web-security",
    "--window-size=1920,1080",
    "--start-maximized",
    "--disable-infobars",
    "--disable-background-timer-throttling",
    "--disable-backgrounding-occluded-windows",
    "--disable-renderer-backgrounding",
]

# Realistic user agents (rotate)
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
]

STEALTH_JS = """
    // ── Remove webdriver flag ────────────────────────────────────────────────
    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });

    // ── Fake plugins ───────────────────────────────────────────────────────
    Object.defineProperty(navigator, 'plugins', {
        get: () => {
            const plugins = [
                { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer' },
                { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai' },
                { name: 'Native Client', filename: 'internal-nacl-plugin' },
            ];
            plugins.length = 3;
            return plugins;
        }
    });

    // ── Fake languages ─────────────────────────────────────────────────────
    Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });

    // ── Fake Chrome runtime ────────────────────────────────────────────────
    window.chrome = { runtime: {}, loadTimes: function(){}, csi: function(){} };

    // ── Fake permissions ───────────────────────────────────────────────────
    const originalQuery = window.navigator.permissions.query;
    window.navigator.permissions.query = (parameters) =>
        parameters.name === 'notifications'
            ? Promise.resolve({ state: Notification.permission })
            : originalQuery(parameters);

    // ── WebGL fingerprint spoofing (Phase 3.4) ─────────────────────────────
    const originalGetParameter = WebGLRenderingContext.prototype.getParameter;
    WebGLRenderingContext.prototype.getParameter = function(parameter) {
        // UNMASKED_RENDERER_WEBGL
        if (parameter === 37445) return 'Intel Inc.';
        // UNMASKED_VENDOR_WEBGL
        if (parameter === 37446) return 'Intel Iris OpenGL Engine';
        return originalGetParameter.call(this, parameter);
    };

    // Spoof WebGL2 renderer
    const ext = document.createElement('canvas').getContext('webgl2').getExtension('WEBGL_debug_renderer_info');
    if (ext) {
        try {
            const gl = document.createElement('canvas').getContext('webgl2');
            gl.getParameter(ext.UNMASKED_RENDERER_WEBGL);
        } catch(e) {}
    }

    // ── Canvas fingerprint spoofing (Phase 3.4) ─────────────────────────────
    const originalToDataURL = HTMLCanvasElement.prototype.toDataURL;
    HTMLCanvasElement.prototype.toDataURL = function(type, quality) {
        const ctx = this.getContext('2d');
        if (ctx) {
            // Add slight noise to canvas pixels to defeat automated fingerprinting
            try {
                const imageData = ctx.getImageData(0, 0, this.width, this.height);
                const data = imageData.data;
                for (let i = 0; i < data.length; i += 4) {
                    data[i]     = data[i]     ^ (Math.random() < 0.5 ? 1 : 0);
                    data[i + 1] = data[i + 1] ^ (Math.random() < 0.5 ? 1 : 0);
                    data[i + 2] = data[i + 2] ^ (Math.random() < 0.5 ? 1 : 0);
                }
                ctx.putImageData(imageData, 0, 0);
            } catch(e) {}
        }
        return originalToDataURL.call(this, type, quality);
    };

    // ── AudioContext fingerprint spoofing (Phase 3.4) ────────────────────────
    const originalCreateAnalyser = AudioContext.prototype.createAnalyser;
    if (originalCreateAnalyser) {
        AudioContext.prototype.createAnalyser = function() {
            const analyser = originalCreateAnalyser.call(this);
            try {
                const param = analyser.frequencyBinCount;
                Object.defineProperty(analyser, 'fftSize', {
                    get: () => 2048,
                    set: (v) => { /* allow */ },
                });
            } catch(e) {}
            return analyser;
        };
    }

    // ── navigator.hardwareConcurrency spoofing (Phase 3.4) ──────────────────
    Object.defineProperty(navigator, 'hardwareConcurrency', { get: () => 8 });

    // ── deviceMemory spoofing ────────────────────────────────────────────────
    if (navigator.deviceMemory === undefined) {
        Object.defineProperty(navigator, 'deviceMemory', { get: () => 8 });
    }

    // ── Remove automation indicators ─────────────────────────────────────────
    delete window.cdc_adoQpoasnfa76pfcZLmcfl_Array;
    delete window.cdc_adoQpoasnfa76pfcZLmcfl_Promise;
    delete window.cdc_adoQpoasnfa76pfcZLmcfl_Symbol;
    delete window.__webdriver_evaluate;
    delete window.__selenium_evaluate;
    delete window.__webdriver_script_function;
    delete window.__webdriver_script_func;
    delete window.__webdriver_script_atoms;
    delete window._selenium;
    delete window.cachedFramebot;

    // ── Randomize automation flags ──────────────────────────────────────────
    const randomProps = ['__webdriver', '__selenium', '__webdriver__', '__selenium__'];
    randomProps.forEach(p => {
        try {
            if (window[p] !== undefined) {
                Object.defineProperty(window, p, {
                    get: () => undefined,
                    configurable: false,
                });
            }
        } catch(e) {}
    });
"""

SYSTEM_PROMPT = """You are a browser automation agent. You control a web browser to complete tasks.

RULES:
- You are ALREADY on the page listed in the page info below — do NOT navigate away
- If the task URL matches the current page URL, work on THIS page immediately
- Only use navigate() if the task explicitly asks you to go to a different URL
- You can return MULTIPLE actions in ONE response — they will be executed in order with small delays between them
- Use the ACTION format exactly as shown, one per line
- Be precise with CSS selectors (use [name="fieldname"] for form fields)
- For radio buttons: use check([name="size"][value="large"])
- For checkboxes: use check([name="topping"][value="bacon"])
- NEVER include quotes around text values in type actions
- Always use RAW text without quotes

Available actions:
- ACTION: navigate(url) — ONLY if you need to go somewhere else
- ACTION: click(selector) — click an element
- ACTION: dblclick(selector) — double-click an element
- ACTION: hover(selector) — hover over an element (for dropdowns, tooltips)
- ACTION: type(selector, text) — type RAW text only, no quotes
- ACTION: select_option(selector, value) — select a <option> from a <select> dropdown
- ACTION: check(selector) — check a checkbox or radio button
- ACTION: submit(selector) — click a form submit button
- ACTION: scroll(direction) — "up" or "down"
- ACTION: wait(seconds) — wait N seconds
- ACTION: screenshot() — take a screenshot
- ACTION: get_text(selector) — extract text content from an element
- ACTION: evaluate(js) — run arbitrary JavaScript, return result as string
- ACTION: switch_to_tab(index) — switch to tab by index (0=first)
- ACTION: done(answer) — complete the task with your answer

Examples (work on the CURRENT page, do not navigate):
Current page: pizza order form at https://httpbin.org/forms/post
Task: Fill in name, email, select large, check bacon, submit

You can do it all in one turn:
ACTION: type(input[name="custname"], John Connor)
ACTION: type(input[name="custemail"], john@example.com)
ACTION: select_option(select[name="size"], large)
ACTION: check(input[name="topping"][value="bacon"])
ACTION: click(button[type="submit"])
ACTION: done(Order submitted successfully)

Or split across turns if you need to observe results between actions.
"""


class BrowserAgent:
    def __init__(self, api_key: Optional[str] = None, model_name: Optional[str] = None):
        self.api_key = api_key or os.getenv("MINIMAX_API_KEY") or os.getenv("OPENAI_API_KEY") or ""
        self.model_name = model_name or os.getenv("AI_MODEL", "MiniMax-M2.7")
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.history: list = []
        self.conversation_history: list = []

    def _build_ai_messages(self, task: str, page_content: str) -> list:
        """Build messages for AI including conversation history"""
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages.extend(self.conversation_history)

        try:
            data = json.loads(page_content) if page_content.startswith("{") else {}
        except:
            data = {}

        form_lines = []
        form_map = data.get("form", {})
        if form_map:
            form_lines.append("FORM FIELDS:")
            for label, info in form_map.items():
                form_lines.append(f"  {label}: {info['selector']} (type={info['type']})")

        # Phase 3.2: include select options
        select_options = data.get("select_options", {})
        if select_options:
            form_lines.append("SELECT DROPDOWNS:")
            for name, info in select_options.items():
                opts = ", ".join(f"'{o['value']}'" + (" [SELECTED]" if o.get("selected") else "") for o in info["options"])
                form_lines.append(f"  {name} ({info['selector']}): {opts}")

        interactives = data.get("interactives", [])
        int_lines = []
        if interactives:
            int_lines.append("INTERACTIVE:")
            for el in interactives:
                if el["tag"] in ("button", "a") or el["type"] in ("submit", "button"):
                    int_lines.append(f"  {el['text'] or el['selector']}: {el['selector']}")
                elif el["tag"] == "input":
                    int_lines.append(f"  [{el['type']}] {el['selector']}: placeholder='{el['placeholder'] or ''}' current='{el.get('value','')}'")

        # Phase 3.2: page state warnings
        warnings = []
        page_state = data.get("page_state", "")
        if page_state == "spa/dynamic":
            warnings.append("⚠ PAGE IS DYNAMIC/SPA — content may load after initial render")
        captcha = data.get("captcha")
        if captcha:
            warnings.append(f"⚠ CAPTCHA DETECTED: {captcha}")
        cookie_banner = data.get("cookie_banner")
        if cookie_banner:
            warnings.append(f"⚠ COOKIE BANNER: {cookie_banner}")
        iframe_count = data.get("iframe_count", 0)
        if iframe_count > 0:
            warnings.append(f"ℹ {iframe_count} iframe(s) on page")
        shadow_dom_count = data.get("shadow_dom_count", 0)
        if shadow_dom_count > 0:
            warnings.append(f"ℹ {shadow_dom_count} shadow DOM element(s)")

        content_parts = [f"Task: {task}"]
        if warnings:
            content_parts.append("PAGE WARNINGS: " + " | ".join(warnings))
        if form_lines:
            content_parts.append("\n".join(form_lines))
        if int_lines:
            content_parts.append("\n".join(int_lines))
        content_parts.append(f"\nPage: {data.get('title','unknown')} — {data.get('url','')}")

        content = "\n".join(content_parts)
        messages.append({"role": "user", "content": content[:1200]})
        return messages

    async def _init_browser(self):
        """Initialize stealth browser"""
        if self.playwright is None:
            self.playwright = await async_playwright().start()

        if self.browser is None:
            self.browser = await self.playwright.chromium.launch(
                args=STEALTH_ARGS,
                headless=True,
                ignore_default_args=["--enable-automation"],
            )

        if self.context is None:
            ua = random.choice(USER_AGENTS)
            self.context = await self.browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent=ua,
                locale="en-US",
                timezone_id="America/New_York",
                extra_http_headers={
                    "Accept-Language": "en-US,en;q=0.9",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                    "Accept-Encoding": "gzip, deflate, br",
                    "Connection": "keep-alive",
                    "Upgrade-Insecure-Requests": "1",
                    "Sec-Fetch-Dest": "document",
                    "Sec-Fetch-Mode": "navigate",
                    "Sec-Fetch-Site": "none",
                    "Sec-Fetch-User": "?1",
                    "Cache-Control": "max-age=0",
                },
                screen={"width": 1920, "height": 1080},
                color_scheme="dark",
            )
            self.page = await self.context.new_page()
            await self.page.add_init_script(STEALTH_JS)
            self.page.set_default_timeout(15000)
            self.page.set_default_navigation_timeout(30000)

    async def _dismiss_cookie_banner(self):
        """Auto-dismiss common cookie consent banners"""
        try:
            await asyncio.sleep(0.5)
            cookie_selectors = [
                "[aria-label='Accept all cookies']",
                "[aria-label='Accept cookies']",
                "[aria-label='Accept']",
                "[aria-label='Agree']",
                "[aria-label='Allow cookies']",
                "[aria-label='Allow all']",
                "[aria-label='Reject all']",
                "[aria-label='Decline all']",
                "[aria-label='Decline cookies']",
                "[aria-label='Dismiss']",
                "[aria-label='Close']",
                "[title='Accept']",
                "[title='Accept all']",
                "[title='Agree']",
                "[title='Allow']",
                "[title='Allow all']",
                "[title='Reject']",
                "[title='Decline']",
                "[title='Dismiss']",
                "[id*='cookie'][aria-label*='accept']",
                "[id*='cookie'][aria-label*='Accept']",
                "[id*='consent'] button",
                "[class*='cookie'] button",
                "[class*='Cookie'] button",
                "[id*='cookie-consent']",
                "[id*='CookieConsent']",
                "[class*='cookie-consent']",
                "[class*='CookieConsent']",
                "[id*='gdpr']",
                "[class*='gdpr']",
                "[id*='privacy-consent']",
                "[class*='privacy-consent']",
                "button[title='Accept all']",
                "button[title='Accept']",
                "button:text('Accept')",
                "button:text('Accept all')",
                "button:text('Accept all cookies')",
                "button:text('Accept cookies')",
                "button:text('Allow')",
                "button:text('Allow all')",
                "button:text('Agree')",
                "button:text('Decline')",
                "button:text('Reject')",
                "button:text('Reject all')",
                "button:text('Dismiss')",
                "button:text('Continue')",
                "button:text('Got it')",
                "button:text('I agree')",
                "input[value='Accept']",
                "input[value='Accept all']",
                "input[value='Allow']",
                "input[value='Agree']",
                "a[aria-label*='accept']",
                "a[aria-label*='Accept']",
            ]
            for selector in cookie_selectors:
                try:
                    elem = await self.page.query_selector(selector)
                    if elem:
                        await elem.click(timeout=2000)
                        await self._human_delay(0.3, 0.6)
                        logger.info(f"Dismissed cookie banner with selector: {selector}")
                        return
                except:
                    continue
        except Exception as e:
            logger.warning(f"Cookie banner dismiss failed: {e}")

    async def _human_scroll(self, direction: str = "down", fraction: float = None):
        """Scroll with human-like randomisation (Phase 3.4).

        Args:
            direction: 'down' or 'up'
            fraction: optional 0.0–1.0 override — fraction of viewport height to scroll.
                      None = random 0.3–0.8 of viewport height.
        """
        if fraction is None:
            fraction = random.uniform(0.3, 0.8)

        if direction == "down":
            sign = -1
        elif direction == "up":
            sign = 1
        else:
            # random direction
            sign = random.choice([-1, 1])

        viewport = self.page.viewport_size or {"width": 1280, "height": 720}
        scroll_px = int(sign * fraction * viewport["height"])

        # Add slight horizontal drift (1–15% of vertical scroll)
        h_drift = int(scroll_px * random.uniform(0.01, 0.15))
        h_drift *= random.choice([-1, 1])

        # Small pause before scroll
        await asyncio.sleep(random.uniform(0.05, 0.2))
        await self.page.evaluate(
            f"(x, y) => window.scrollBy({{ top: {scroll_px}, left: {h_drift}, behavior: 'smooth' }})",
            0, 0
        )
        # Pause after scroll to let animation settle
        await asyncio.sleep(random.uniform(0.2, 0.5))

    async def _human_move(self, target_x: int, target_y: int):
        """Move mouse to target position via bezier curve (Phase 3.4).

        Replaces plain page.mouse.move() with a multi-step curved path
        that accelerates then decelerates — much harder to detect as bot.
        """
        start_x = random.randint(50, 700)
        start_y = random.randint(50, 500)

        # 4–8 waypoints for a natural-looking curve
        steps = random.randint(4, 8)
        duration_ms = random.randint(400, 1000)
        step_ms = duration_ms / steps

        # Bezier control points — make it arc naturally above/below the straight line
        cp1x = start_x + (target_x - start_x) * random.uniform(0.2, 0.4)
        cp1y = start_y + (target_y - start_y) * random.uniform(-0.4, -0.1)  # arc upward
        cp2x = start_x + (target_x - start_x) * random.uniform(0.6, 0.8)
        cp2y = start_y + (target_y - start_y) * random.uniform(1.1, 1.4)   # arc downward

        # Generate points along cubic bezier
        import math
        points = []
        for t in [i / steps for i in range(steps + 1)]:
            t2 = t * t
            t3 = t2 * t
            mt = 1 - t
            mt2 = mt * mt
            mt3 = mt2 * mt
            px = mt3 * start_x + 3 * mt2 * t * cp1x + 3 * mt * t2 * cp2x + t3 * target_x
            py = mt3 * start_y + 3 * mt2 * t * cp1y + 3 * mt * t2 * cp2y + t3 * target_y
            # Add micro-jitter
            px += random.gauss(0, 1.5)
            py += random.gauss(0, 1.5)
            points.append((round(px, 1), round(py, 1)))

        for i, (x, y) in enumerate(points):
            await self.page.mouse.move(x, y)
            # Slow down near the end (deceleration)
            delay = step_ms * (1.5 if i > steps * 0.7 else 1.0)
            await asyncio.sleep(delay / 1000)

    async def _human_delay(self, min_s: float = 0.5, max_s: float = 2.0):
        """Random delay mimicking human speed"""
        await asyncio.sleep(random.uniform(min_s, max_s))

    async def _get_page_content(self) -> str:
        """Get rich structured page content for AI — includes SPA detection, selects, iframes, CAPTCHAs."""
        try:
            # First wait briefly for dynamic content to settle
            try:
                await self.page.wait_for_load_state("networkidle", timeout=3000)
            except Exception:
                pass

            content = await self.page.evaluate("""() => {
                const body = document.body;
                if (!body) return JSON.stringify({error: 'Empty page'});

                // ── SPA / dynamic page detection ──────────────────────────────────
                const networkRequests = window.performance && window.performance.getEntries
                    ? window.performance.getEntriesByType('resource').length : -1;
                const hasMutationObserver = typeof MutationObserver !== 'undefined';
                const hasPendingRequests = document.readyState !== 'complete';

                // ── Cookie / consent banner detection ─────────────────────────────
                const cookieBannerSelectors = [
                    '[aria-label*="cookie" i]', '[class*="cookie" i]', '[id*="cookie" i]',
                    '[class*="consent" i]', '[id*="consent" i]', '[class*="gdpr" i]',
                    '[aria-label*="accept" i]', '[aria-label*="allow" i]',
                ];
                let cookieBannerDetected = null;
                for (const sel of cookieBannerSelectors) {
                    const el = document.querySelector(sel);
                    if (el && window.getComputedStyle(el).display !== 'none') {
                        cookieBannerDetected = sel;
                        break;
                    }
                }

                // ── CAPTCHA / Cloudflare detection ───────────────────────────────
                let captchaDetected = null;
                const cfChallenge = document.querySelector('#cf-challenge-center, #challenge-form, .cf-challenge');
                const hcaptcha = document.querySelector('.h-captcha');
                const recaptcha = document.querySelector('.g-recaptcha');
                const genericCaptcha = document.querySelector('[class*="captcha" i], [id*="captcha" i]');
                if (cfChallenge) captchaDetected = 'cloudflare';
                else if (hcaptcha) captchaDetected = 'hcaptcha';
                else if (recaptcha) captchaDetected = 'recaptcha';
                else if (genericCaptcha) captchaDetected = 'generic';

                // ── Shadow DOM elements ──────────────────────────────────────────
                const shadowHosts = document.querySelectorAll('*');
                let shadowDomCount = 0;
                for (const el of shadowHosts) {
                    if (el.shadowRoot) shadowDomCount++;
                }

                // ── Iframe count ────────────────────────────────────────────────
                const iframes = document.querySelectorAll('iframe');
                const iframeInfo = Array.from(iframes).map(f => ({
                    src: f.src ? f.src.slice(0, 80) : '',
                    visible: f.offsetWidth > 0 && f.offsetHeight > 0,
                }));

                // ── ARIA live regions ───────────────────────────────────────────
                const ariaLive = Array.from(document.querySelectorAll('[aria-live]'))
                    .map(el => ({ tag: el.tagName.toLowerCase(), text: el.textContent.trim().slice(0, 60), politeness: el.getAttribute('aria-live') }));

                // ── Select options ─────────────────────────────────────────────
                const selectMap = {};
                document.querySelectorAll('select').forEach(sel => {
                    const name = sel.getAttribute('name') || sel.id || sel.className || sel.tagName.toLowerCase();
                    const options = Array.from(sel.options).map(opt => ({
                        text: opt.text.trim().slice(0, 60),
                        value: opt.value,
                        selected: opt.selected,
                    }));
                    selectMap[name] = { selector: (sel.getAttribute('name') ? `select[name="${sel.getAttribute('name')}"]` : sel.id ? `#${sel.id}` : sel.tagName.toLowerCase()), options };
                });

                // ── Image alt text ─────────────────────────────────────────────
                const images = Array.from(document.images).slice(0, 20).map(img => ({
                    alt: img.alt || '',
                    src: img.src ? img.src.slice(0, 80) : '',
                    width: img.naturalWidth,
                }));

                const walker = document.createTreeWalker(body, NodeFilter.SHOW_TEXT, {
                    acceptNode: (node) => {
                        const style = window.getComputedStyle(node.parentElement);
                        return style.display !== 'none' && style.visibility !== 'hidden'
                            ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT;
                    }
                });

                const texts = [];
                while (walker.nextNode()) {
                    const t = walker.currentNode.textContent.trim();
                    if (t) texts.push(t);
                }

                const formMap = {};
                document.querySelectorAll('input, select, textarea').forEach(el => {
                    const name = el.getAttribute('name') || el.id || '';
                    const type = el.getAttribute('type') || '';
                    const value = el.getAttribute('value') || '';
                    let label = '';
                    const forAttr = el.getAttribute('id');
                    if (forAttr) {
                        const lbl = document.querySelector('label[for="' + forAttr + '"]');
                        if (lbl) label = lbl.textContent.trim();
                    }
                    if (!label && name) {
                        const lbl = document.querySelector('label[for="' + name + '"]');
                        if (lbl) label = lbl.textContent.trim();
                    }
                    const hint = type === 'radio' || type === 'checkbox' ? `[value="${value}"]` : '';
                    const selector = name ? `${el.tagName.toLowerCase()}[name="${name}"]` : (el.id ? '#' + el.id : el.tagName.toLowerCase());
                    const key = label || (type === 'radio' || type === 'checkbox' ? value : name || selector);
                    formMap[key] = {selector: selector + hint, type, value};
                });

                const interactives = [];
                document.querySelectorAll('a, button, input, select, textarea, [role="button"], [onclick]').forEach(el => {
                    const tag = el.tagName.toLowerCase();
                    const text = el.textContent?.trim()?.slice(0, 50) || '';
                    const href = el.getAttribute('href') || '';
                    const type = el.getAttribute('type') || '';
                    const name = el.getAttribute('name') || '';
                    const id = el.getAttribute('id') || '';
                    const cls = el.getAttribute('class') || '';
                    const placeholder = el.getAttribute('placeholder') || '';

                    let selector = '';
                    if (id) selector = '#' + id;
                    else if (name) selector = `${tag}[name="${name}"]`;
                    else if (cls) selector = `${tag}.${cls.split(' ')[0]}`;
                    else selector = tag;

                    interactives.push({
                        selector,
                        tag,
                        text: text.slice(0, 30),
                        href: href.slice(0, 50),
                        type,
                        placeholder: placeholder.slice(0, 30),
                        value: (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA') ? (el.value || '') : '',
                    });
                });

                return JSON.stringify({
                    url: window.location.href,
                    title: document.title,
                    text: texts.slice(0, 100).join(' ').slice(0, 2000),
                    form: formMap,
                    interactives: interactives.slice(0, 30),
                    // Phase 3.2 enriched fields
                    page_state: hasPendingRequests ? 'spa/dynamic' : 'static',
                    cookie_banner: cookieBannerDetected,
                    captcha: captchaDetected,
                    shadow_dom_count: shadowDomCount,
                    iframes: iframeInfo,
                    iframe_count: iframes.length,
                    aria_live: ariaLive.slice(0, 5),
                    select_options: selectMap,
                    images: images.slice(0, 10),
                    network_requests: networkRequests,
                });
            }""")
            return content
        except Exception as e:
            return json.dumps({"error": str(e), "url": str(self.page.url if self.page else "none")})

    def _parse_page_data(self, page_content: str) -> dict:
        """Extract structured observation from page content for frontend"""
        try:
            data = json.loads(page_content) if page_content.startswith("{") else {}
        except:
            data = {}
        return data

    async def _call_ai(self, task: str, page_content: str) -> tuple[str, float, str]:
        """Call AI model to decide next action.
        Returns (ai_response, duration_ms, model_name).
        Retries up to 3 times with exponential backoff on API errors."""
        start = time.monotonic()
        model_name = self.model_name
        api_key = self.api_key

        if not api_key:
            logger.warning("No API key available, using fallback AI")
            return self._fallback_ai(task, page_content), (time.monotonic() - start) * 1000, "fallback"

        last_error = None
        for attempt in range(3):
            try:
                from openai import OpenAI

                base_url = os.getenv("MINIMAX_BASE_URL", "https://api.minimax.io/v1")
                client = OpenAI(api_key=api_key, base_url=base_url)
                messages = self._build_ai_messages(task, page_content)
                response = client.chat.completions.create(
                    model=model_name,
                    messages=messages,
                    max_tokens=600,
                    temperature=0.3,
                )
                ai_response = response.choices[0].message.content.strip()
                self.conversation_history.append({"role": "user", "content": f"Task: {task}\n\nPage state:\n{page_content[:1000]}"})
                self.conversation_history.append({"role": "assistant", "content": ai_response})
                if len(self.conversation_history) > 6:
                    self.conversation_history = self.conversation_history[-6:]
                return ai_response, (time.monotonic() - start) * 1000, model_name

            except Exception as e:
                last_error = str(e)
                logger.warning(f"AI call failed (attempt {attempt + 1}/3): {last_error}")
                if attempt < 2:  # don't sleep on last attempt
                    delay = 2 ** attempt  # 1s, 2s
                    logger.info(f"Retrying in {delay}s...")
                    await asyncio.sleep(delay)
                    continue

        # All retries exhausted — return fallback with error context so UI can show it
        error_msg = f"API error after 3 retries: {last_error}"
        logger.error(error_msg)
        fallback_response = self._fallback_ai(task, page_content)
        # Tag the fallback so the UI knows this failed
        return f"[ERROR: {last_error[:80]}] {fallback_response}", (time.monotonic() - start) * 1000, "error"

    def _fallback_ai(self, task: str, page_content: str) -> str:
        """Rule-based fallback when AI is unavailable"""
        try:
            data = json.loads(page_content) if page_content.startswith("{") else {}
            title = data.get("title", "")
            text = data.get("text", "")

            task_lower = task.lower()

            if "title" in task_lower or "what" in task_lower:
                return f'ACTION: done(The page title is "{title}". Text on page: {text[:200]})'
            if "text" in task_lower or "content" in task_lower or "visible" in task_lower:
                return f'ACTION: done(Visible text: {text[:500]})'
            if "screenshot" in task_lower:
                return "ACTION: screenshot()"
            if "click" in task_lower:
                interactives = data.get("interactives", [])
                if interactives:
                    target = interactives[0]
                    return f'ACTION: click({target["selector"]})'
                return f'ACTION: done(No clickable elements found. Page title: {title})'

            return f'ACTION: done(Page title: "{title}". Content: {text[:300]})'
        except:
            return f'ACTION: done(Could not parse page. Task was: {task})'

    def _parse_actions(self, response: str) -> list[tuple[str, str]]:
        """Parse AI response into list of (action, argument) tuples — supports batching."""
        actions = []
        for line in response.split("\n"):
            line = line.strip()
            if line.startswith("ACTION:"):
                rest = line[7:].strip()
                if "(" in rest and rest.endswith(")"):
                    name = rest[:rest.index("(")].strip()
                    arg = rest[rest.index("(")+1:-1].strip()
                    actions.append((name, arg))
                else:
                    # Bare "done" or "screenshot" etc without parens
                    parts = rest.split(None, 1)
                    if parts:
                        name = parts[0].lower()
                        arg = parts[1] if len(parts) > 1 else ""
                        actions.append((name, arg))
        return actions if actions else [("done", response[:200])]

    def _parse_action(self, response: str) -> tuple[str, str]:
        """Legacy single-action parser — delegates to _parse_actions."""
        actions = self._parse_actions(response)
        return actions[0]

    async def _retry_intelligent(self, action: str, arg: str, error_msg: str) -> tuple[bool, dict]:
        """On action failure, try alternative approaches before giving up.

        Returns (success, result_dict).
        """
        result = {"success": False, "error": error_msg}

        # ── Click failures: try alternate selectors ─────────────────────────────
        if action == "click":
            try:
                # Try JS click as fallback
                alt_js = f"""
                (function() {{
                    var el = document.querySelector('{arg}');
                    if (el) {{ el.click(); return 'clicked'; }}
                    // Try text-based search
                    var all = document.querySelectorAll('button, a, [role="button"]');
                    for (var i = 0; i < all.length; i++) {{
                        if (all[i].textContent.trim().toLowerCase().includes('{arg.lower()}')) {{
                            all[i].click(); return 'clicked_by_text';
                        }}
                    }}
                    return 'not_found';
                }})();
                """
                js_result = await self.page.evaluate(alt_js)
                if js_result in ("clicked", "clicked_by_text"):
                    await self._human_delay(0.3, 0.8)
                    return True, {"success": True}
            except Exception as js_err:
                logger.warning(f"JS click fallback failed: {js_err}")

        # ── Type failures: try fill with delay, or evaluate ─────────────────
        if action == "type":
            try:
                parts = arg.split(",", 1)
                if len(parts) == 2:
                    selector, text = parts[0].strip(), parts[1].strip()
                    # Remove quotes if present
                    if (text.startswith('"') and text.endswith('"')) or \
                       (text.startswith("'") and text.endswith("'")):
                        text = text[1:-1]
                    # Escape single quotes for JS string
                    text_escaped = text.replace("'", "\\'")
                    js_code = (
                        "(function() {"
                        "var el = document.querySelector('%s');"
                        "if (el) { el.focus(); el.value = '%s'; "
                        "el.dispatchEvent(new Event('input', { bubbles: true })); "
                        "el.dispatchEvent(new Event('change', { bubbles: true })); "
                        "return 'typed'; }"
                        "return 'not_found';"
                        "})();" % (selector, text_escaped)
                    )
                    js_result = await self.page.evaluate(js_code)
                    if js_result == "typed":
                        await self._human_delay(0.3, 0.6)
                        return True, {"success": True}
            except Exception as js_err:
                logger.warning("JS type fallback failed: %s", js_err)

        if action == "check":
            try:
                js_code = (
                    "(function() {"
                    "var el = document.querySelector('%s');"
                    "if (el) { el.checked = true; "
                    "el.dispatchEvent(new Event('change', { bubbles: true })); "
                    "return 'checked'; }"
                    "return 'not_found';"
                    "})();" % arg
                )
                js_result = await self.page.evaluate(js_code)
                if js_result == "checked":
                    await self._human_delay(0.2, 0.5)
                    return True, {"success": True}
            except Exception as js_err:
                logger.warning(f"JS check fallback failed: {js_err}")

        # ── Evaluate failures: try alternate JS approaches ─────────────────────
        if action == "evaluate":
            try:
                # Try wrapping in try-catch and return structured result
                alt_js = f"""
                (function() {{
                    try {{
                        var __result = ({arg});
                        return JSON.stringify({{ok: true, result: __result}});
                    }} catch(e) {{
                        return JSON.stringify({{ok: false, error: e.message}});
                    }}
                }})();
                """
                js_result = await self.page.evaluate(alt_js)
                import json as _json
                parsed = _json.loads(js_result)
                if parsed.get("ok"):
                    await self._human_delay(0.2, 0.5)
                    return True, {"success": True, "answer": str(parsed.get("result", ""))[:500]}
                else:
                    # Try simpler eval without IIFE wrapping
                    simple_result = await self.page.evaluate(arg)
                    await self._human_delay(0.2, 0.5)
                    return True, {"success": True, "answer": str(simple_result)[:500]}
            except Exception as js_err:
                logger.warning(f"JS evaluate fallback failed: {js_err}")

        return False, result

    async def _execute_action(self, action: str, arg: str) -> dict:
        """Execute a single browser action"""
        result = {"action": action, "arg": arg, "success": False, "error": None, "selector": arg}

        try:
            if action == "navigate":
                url = arg if arg.startswith("http") else f"https://{arg}"
                await self.page.goto(url, wait_until="domcontentloaded", timeout=30000)
                await self._human_delay(0.5, 1.5)
                await self._dismiss_cookie_banner()
                result["success"] = True
                result["url"] = self.page.url

            elif action == "click":
                try:
                    # Use commit to avoid hanging on button clicks that don't navigate
                    await self.page.click(arg, wait_for_load_state="commit", timeout=5000)
                    await self._human_delay(0.3, 1.0)
                    result["success"] = True
                except Exception as e:
                    clicked = False
                    try:
                        submit_texts = ["submit", "submit order", "submit"]
                        for text in submit_texts:
                            btns = await self.page.query_selector_all("button, input[type='submit'], [type='submit']")
                            for btn in btns:
                                btn_text = (await btn.inner_text()).lower().strip()
                                btn_type = await btn.get_attribute("type") or ""
                                if text in btn_text or btn_type == "submit":
                                    await btn.click()
                                    await self._human_delay(0.3, 1.0)
                                    result["success"] = True
                                    clicked = True
                                    break
                            if clicked:
                                break
                    except:
                        pass
                    if not clicked:
                        try:
                            await self.page.click(arg, timeout=8000)
                            await self._human_delay(0.3, 1.0)
                            result["success"] = True
                        except:
                            result["error"] = f"Click failed for '{arg}': {str(e)[:80]}"
                            result["success"] = False

            elif action == "type":
                parts = arg.split(",", 1)
                if len(parts) == 2:
                    selector, text = parts[0].strip(), parts[1].strip()
                    if (text.startswith('"') and text.endswith('"')) or \
                       (text.startswith("'") and text.endswith("'")):
                        text = text[1:-1]
                    # Check if field already has content — triple-click to select all before filling
                    # to avoid double-typing on pre-filled or re-visited fields
                    try:
                        current_val = await self.page.eval_on_selector(selector, "el => el.value")
                        if current_val:
                            await self.page.click(selector)
                            await self.page.keyboard.press("Control+a")
                            await self.page.keyboard.type(text, delay=random.uniform(30, 80))
                        else:
                            await self.page.fill(selector, text, no_wait_after=True)
                    except Exception:
                        # Fallback: just fill
                        await self.page.fill(selector, text, no_wait_after=True)
                    await self._human_delay(0.2, 0.6)
                    result["success"] = True
                else:
                    result["error"] = "Invalid type format: use selector, text"

            elif action == "check":
                try:
                    # no_wait_after to avoid hanging on elements that don't trigger network changes
                    await self.page.check(arg, timeout=5000, no_wait_after=True)
                    await self._human_delay(0.1, 0.3)
                    result["success"] = True
                except Exception as e:
                    try:
                        await self.page.click(arg, wait_for_load_state="commit", timeout=5000)
                        await self._human_delay(0.1, 0.3)
                        result["success"] = True
                    except:
                        result["error"] = f"Check failed for '{arg}': {str(e)[:80]}"
                        result["success"] = False

            elif action == "select":
                # Proper <select> interaction — open dropdown then pick option by text
                try:
                    parts = arg.rsplit(",", 1)
                    if len(parts) == 2:
                        # format: "select[name=size], large" — select by option text
                        sel, opt_text = parts[0].strip(), parts[1].strip()
                        await self.page.click(sel)
                        await asyncio.sleep(0.2)
                        # Click option by text match
                        opt_xpath = f"//option[contains(text(),'{opt_text}')]"
                        await self.page.click(f"{sel} >> xpath={opt_xpath}", timeout=3000)
                    else:
                        # Just a selector — click to open the dropdown
                        await self.page.click(arg)
                    await self._human_delay(0.1, 0.3)
                    result["success"] = True
                except Exception as e:
                    # Fallback: try native select_option
                    try:
                        el = await self.page.query_selector(arg)
                        if el and el.get_attribute("tagName", "").lower() == "select":
                            await el.select_option(arg)
                        else:
                            await self.page.click(arg)
                        await self._human_delay(0.1, 0.3)
                        result["success"] = True
                    except Exception:
                        result["error"] = f"select failed: {str(e)[:80]}"

            elif action == "select_option":
                # arg format: "selector, value"
                parts = arg.rsplit(",", 1)
                if len(parts) == 2:
                    selector = parts[0].strip()
                    value = parts[1].strip()
                    try:
                        el = await self.page.query_selector(selector)
                        if el:
                            await el.select_option(value)
                            await self._human_delay(0.1, 0.3)
                            result["success"] = True
                        else:
                            result["error"] = f"No <select> found at {selector}"
                    except Exception as e:
                        result["error"] = f"select_option failed: {str(e)[:80]}"
                else:
                    result["error"] = "Invalid select_option format: use selector, value"

            elif action == "hover":
                try:
                    await self.page.hover(arg, timeout=5000)
                    await self._human_delay(0.2, 0.5)
                    result["success"] = True
                except Exception as e:
                    result["error"] = f"Hover failed: {str(e)[:80]}"

            elif action == "dblclick":
                try:
                    await self.page.dblclick(arg, timeout=5000, wait_for_load_state="commit")
                    await self._human_delay(0.3, 0.8)
                    result["success"] = True
                except Exception as e:
                    result["error"] = f"dblclick failed: {str(e)[:80]}"

            elif action == "switch_to_tab":
                try:
                    idx = int(arg)
                    pages = self.context.pages
                    if 0 <= idx < len(pages):
                        await pages[idx].bring_to_front()
                        self.page = pages[idx]
                        await self._human_delay(0.3, 0.6)
                        result["success"] = True
                    else:
                        result["error"] = f"Tab index {idx} out of range (have {len(pages)} tabs)"
                except Exception as e:
                    result["error"] = f"switch_to_tab failed: {str(e)[:80]}"

            elif action == "get_text":
                try:
                    el = await self.page.query_selector(arg)
                    if el:
                        text = (await el.inner_text())[:500]
                        result["success"] = True
                        result["answer"] = text
                    else:
                        result["error"] = f"No element found at {arg}"
                except Exception as e:
                    result["error"] = f"get_text failed: {str(e)[:80]}"

            elif action == "evaluate":
                try:
                    js_result = await self.page.evaluate(arg)
                    result["success"] = True
                    result["answer"] = str(js_result)[:500]
                except Exception as e:
                    result["error"] = f"evaluate failed: {str(e)[:80]}"

            elif action == "submit":
                # Use wait_for_load_state=commit so we don't hang waiting for a POST response
                # that doesn't navigate anywhere (e.g. httpbin.org/post)
                try:
                    await asyncio.wait_for(
                        self.page.click(arg, wait_for_load_state="commit"),
                        timeout=15.0
                    )
                except asyncio.TimeoutError:
                    # Fallback: just click without waiting
                    try:
                        await self.page.click(arg, wait_for_load_state="commit", timeout=8000)
                    except Exception:
                        pass
                await self._human_delay(0.5, 1.5)
                result["success"] = True

            elif action == "scroll":
                amount = random.randint(300, 700)
                direction = amount if arg == "down" else -amount
                await self.page.mouse.wheel(0, direction)
                await self._human_delay(0.3, 0.8)
                result["success"] = True

            elif action == "wait":
                seconds = min(float(arg), 10)
                await asyncio.sleep(seconds)
                result["success"] = True

            elif action == "screenshot":
                result["success"] = True
                result["screenshot"] = True

            elif action == "done":
                result["success"] = True
                result["answer"] = arg

        except Exception as e:
            result["error"] = str(e)[:200]

        return result

    async def _take_screenshot(self) -> str:
        """Take screenshot and return base64"""
        if self.page:
            try:
                ss = await asyncio.wait_for(
                    self.page.screenshot(type="png", full_page=False),
                    timeout=10.0
                )
                return base64.b64encode(ss).decode()
            except asyncio.TimeoutError:
                return ""
            except Exception:
                return ""
        return ""

    async def stream_execute(self, task: str, url: str, mode: str) -> AsyncGenerator[dict, None]:
        """Stream step-by-step execution via WebSocket — FULL rich step data"""
        await self._init_browser()

        steps_executed = 0
        max_steps = 15 if mode == "fast" else (25 if mode == "deep" else 15)

        # Navigate to start
        nav_start = time.monotonic()
        try:
            await self.page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await self._dismiss_cookie_banner()
            steps_executed += 1
            nav_ms = int((time.monotonic() - nav_start) * 1000)
            yield {
                "step": steps_executed,
                "action": "navigate",
                "argument": url,
                "status": "completed",
                "url": self.page.url,
                "page_title": await self.page.title() if self.page else "",
                "duration_ms": nav_ms,
                "model": "playwright",
                "screenshot": await self._take_screenshot(),
                "observation": f"Loaded {url}",
            }
        except Exception as e:
            yield {
                "step": 0, "action": "error", "error": f"Navigation failed: {str(e)}",
                "status": "failed", "duration_ms": int((time.monotonic() - nav_start) * 1000),
            }
            return

        for step_num in range(2, max_steps + 1):
            # Get page state
            page_content = await self._get_page_content()
            page_data = self._parse_page_data(page_content)
            page_title_val = await self.page.title() if self.page else ""
            page_url = page_data.get("url", "")

            # Build observation summary for frontend
            form_fields = list(page_data.get("form", {}).keys())
            interactives = page_data.get("interactives", [])
            buttons = [i["text"] or i["selector"] for i in interactives if i["tag"] in ("button", "a") or i["type"] in ("submit", "button")]

            observation_parts = []
            if form_fields:
                observation_parts.append(f"Forms: {', '.join(form_fields[:8])}")
            if buttons:
                observation_parts.append(f"Buttons: {', '.join(buttons[:6])}")
            if page_title_val:
                observation_parts.append(f"Title: {page_title_val}")
            observation = " | ".join(observation_parts) or f"Page at {page_url}"

            # Call AI
            ai_response, ai_ms, model_name = await self._call_ai(task, page_content)

            # If API failed after all retries, surface error and stop
            if model_name == "error":
                yield {
                    "step": step_num,
                    "action": "error",
                    "argument": "",
                    "status": "failed",
                    "url": page_url,
                    "page_title": page_title_val,
                    "model": "error",
                    "duration_ms": int(ai_ms),
                    "ai_reasoning": ai_response,
                    "observation": f"API error: {ai_response[:200]}",
                    "screenshot": await self._take_screenshot(),
                    "error": ai_response[:200],
                }
                return

            action, arg = self._parse_action(ai_response)
            # Always parse all actions for batching support
            all_actions = self._parse_actions(ai_response)

            # Send ONE thinking step showing all planned actions
            yield {
                "step": step_num,
                "action": all_actions[0][0],
                "argument": all_actions[0][1][:150] if all_actions[0][1] else "",
                "status": "thinking",
                "url": page_url,
                "page_title": page_title_val,
                "model": model_name,
                "duration_ms": int(ai_ms),
                "ai_reasoning": ai_response,
                "observation": observation,
                "screenshot": None,
                "thinking": (
                    f"[{model_name} · {ai_ms:.0f}ms]\n"
                    f"Looking at: {page_title_val}\n"
                    f"Task: {task[:80]}{'...' if len(task) > 80 else ''}\n"
                    f"Observation: {observation[:200]}\n"
                    f"Decision:\n" + "\n".join(f"  {i+1}. {a[0]}({a[1][:80]})" for i, a in enumerate(all_actions))
                ),
            }

            # Execute all actions in sequence
            for batch_idx, (action, arg) in enumerate(all_actions):
                exec_start = time.monotonic()
                try:
                    result = await asyncio.wait_for(
                        self._execute_action(action, arg),
                        timeout=30.0
                    )
                except asyncio.TimeoutError:
                    result = {"success": False, "error": f"Step timed out after 30s (action: {action})"}
                exec_ms = int((time.monotonic() - exec_start) * 1000)

                # If this is get_text or evaluate, carry the answer through
                answer_val = result.get("answer", "")

                if result["success"]:
                    steps_executed += 1

                    if action == "done":
                        yield {
                            "step": step_num,
                            "action": "done",
                            "argument": answer_val or arg,
                            "status": "completed",
                            "url": self.page.url if self.page else page_url,
                            "page_title": await self.page.title() if self.page else page_title_val,
                            "duration_ms": exec_ms,
                            "model": model_name,
                            "ai_reasoning": ai_response,
                            "observation": observation,
                            "screenshot": await self._take_screenshot(),
                            "answer": answer_val or arg,
                        }
                        return
                    elif result.get("screenshot"):
                        pass

                    # Send SUCCESS snapshot for this action
                    screenshot = await self._take_screenshot()
                    yield {
                        "step": step_num,
                        "action": action,
                        "argument": arg[:150] if arg else "",
                        "status": "completed",
                        "url": self.page.url if self.page else page_url,
                        "page_title": await self.page.title() if self.page else page_title_val,
                        "duration_ms": exec_ms,
                        "model": model_name,
                        "ai_reasoning": ai_response,
                        "observation": observation,
                        "screenshot": screenshot,
                        "error": None,
                    }

                    # If get_text/evaluate, surface the extracted value in observation
                    # Only take screenshot if the page actually changed (not for pure reads)
                    if answer_val:
                        pass  # skip extra screenshot for read-only actions
                else:
                    # ── Retry intelligence ─────────────────────────────────────────
                    retry_success = False
                    if not result["success"]:
                        error_msg = result.get("error", "")
                        retry_success, retry_result = await self._retry_intelligent(action, arg, error_msg)
                        if retry_success:
                            result = retry_result

                    if not retry_success:
                        yield {
                            "step": step_num,
                            "action": "error",
                            "argument": arg[:150] if arg else "",
                            "status": "retrying",
                            "url": page_url,
                            "page_title": page_title_val,
                            "duration_ms": exec_ms,
                            "model": model_name,
                            "ai_reasoning": ai_response,
                            "observation": observation,
                            "screenshot": await self._take_screenshot(),
                            "error": result.get("error", "Unknown error"),
                            "retry_count": 1,
                        }
                        # Stop execution of remaining batch actions on failure
                        break

                # Small human delay between batched actions
                await self._human_delay(0.3, 0.8)

        # Max steps reached
        yield {
            "step": steps_executed,
            "action": "done",
            "argument": f"Reached maximum steps ({max_steps})",
            "status": "completed",
            "url": self.page.url if self.page else "",
            "page_title": await self.page.title() if self.page else "",
            "duration_ms": 0,
            "model": model_name,
            "screenshot": await self._take_screenshot(),
        }

    async def cleanup(self):
        """Clean up all resources"""
        try:
            if self.page and not self.page.is_closed():
                await self.page.close()
        except:
            pass
        self.page = None

        try:
            if self.context:
                await self.context.close()
        except:
            pass
        self.context = None

        try:
            if self.browser:
                await self.browser.close()
        except:
            pass
        self.browser = None

        try:
            if self.playwright:
                await self.playwright.stop()
        except:
            pass
        self.playwright = None
