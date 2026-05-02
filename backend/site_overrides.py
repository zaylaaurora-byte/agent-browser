"""
site_overrides.py — T031: Site-specific antibot bypass patterns.

Known commercial sites that block headless browsers — and the specific
header sets, navigation strategies, and proxy requirements to bypass them.

Each override applies when the target domain matches. Overrides are applied
AFTER the browser context is created, before navigation.

Usage in browser_agent.py:
    from site_overrides import SITE_OVERRIDES, apply_site_override
    override = SITE_OVERRIDES.get(parsed_domain)
    if override:
        await apply_site_override(page, override)
"""

from typing import Optional
from dataclasses import dataclass, field
from typing import Callable


@dataclass
class SiteOverride:
    """Site-specific antibot bypass configuration."""

    # Human-readable site name
    name: str

    # Domains this override applies to (exact or suffix match)
    domains: list[str]

    # Additional headers to inject BEFORE navigation
    # These are set via page.set_extra_http_headers() before goto()
    extra_headers: dict[str, str] = field(default_factory=dict)

    # JavaScript to evaluate before navigation (pre-navigation setup)
    pre_nav_js: str = ""

    # JavaScript to evaluate after first page load (post-navigation fixes)
    post_nav_js: str = ""

    # Delay in seconds BEFORE navigation (let proxy warm up)
    pre_nav_delay: float = 0.0

    # Delay in seconds AFTER navigation (let challenge pages settle)
    post_nav_delay: float = 1.5

    # Whether to use a proxy (some sites require residential IP regardless)
    requires_proxy: bool = True

    # Proxy provider recommendation for this site
    recommended_proxy: str = "brightdata-unblock"

    # Navigation strategy hints for the AI
    strategy_note: str = ""

    # Additional cookies to set before navigation
    seed_cookies: dict[str, str] = field(default_factory=dict)

    # Custom user agent (override the random one)
    user_agent: Optional[str] = None

    # Whether to skip the challenge iframe dismissal (some sites use iframes legitimately)
    skip_iframe_dismiss: bool = False

    # Function to call instead of page.goto() — for sites with special navigation
    custom_navigate: Optional[Callable] = None

    # Accept-Language override
    accept_language: str = "en-US,en;q=0.9"

    # Whether to enable cookies from previous sessions (some sites need cookie history)
    preserve_cookies: bool = True

    # Notes about why this works
    notes: str = ""


# ── Known antibot sites and their bypass strategies ─────────────────────────────

SITE_OVERRIDES: dict[str, SiteOverride] = {

    # ── Indeed ──────────────────────────────────────────────────────────────────
    "www.indeed.com": SiteOverride(
        name="Indeed.com",
        domains=["www.indeed.com", "indeed.com"],
        requires_proxy=True,
        recommended_proxy="brightdata-unblock",
        preserve_cookies=True,
        extra_headers={
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "sec-ch-ua": '"Chromium";v="136", "Google Chrome";v="136", "Not.A.Brand";v="99"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "sec-fetch-dest": "document",
            "sec-fetch-mode": "navigate",
            "sec-fetch-site": "none",
            "sec-fetch-user": "?1",
            "upgrade-insecure-requests": "1",
            "Referer": "https://www.google.com/",
        },
        post_nav_delay=2.5,
        strategy_note=(
            "Indeed uses Cloudflare + their own bot detection. "
            "Use brightdata-unblock proxy. BROWSER_ENGINE=camoufox helps with TLS fingerprint."
        ),
        notes="Cloudflare Ray ID + akamai bot management.",
    ),

    # ── Domino's ───────────────────────────────────────────────────────────────
    "www.dominos.com": SiteOverride(
        name="Domino's Pizza",
        domains=["www.dominos.com", "dominos.com"],
        requires_proxy=True,
        recommended_proxy="brightdata-unblock",
        preserve_cookies=False,  # Fresh session better for ordering
        # Domino's uses PerimeterX / DataDome for bot detection
        extra_headers={
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "sec-fetch-dest": "document",
            "sec-fetch-mode": "navigate",
            "sec-fetch-site": "same-origin",
            # Domino's checks for Google Fonts (absence = bot)
            "Referer": "https://www.google.com/",
        },
        post_nav_delay=2.0,
        # Domino's detects headless via CSS :has() — check for presence of .SRP results
        post_nav_js="""
            (function() {
                // Check if page is a PerimeterX challenge
                const body = document.body ? document.body.innerHTML : '';
                if (body.includes('PerimeterX') || body.includes('px-captcha')) {
                    console.log('[DOMINOS] PerimeterX challenge detected');
                }
                // Trigger fake interaction signals
                ['mouseover', 'mousemove'].forEach(evt => {
                    document.addEventListener(evt, () => {}, { passive: true });
                });
            })();
        """,
        strategy_note=(
            "Domino's uses PerimeterX. Use brightdata-unblock proxy. "
            "Pre-warm cookies by visiting google.com first, then dominos.com. "
            "DO NOT navigate directly from another commercial site (cross-site cookies flag bot)."
        ),
        notes="Detects via CSS :has() selector for headless indicators. Pre-navigation: visit google.com first.",
    ),

    # ── Booking.com ─────────────────────────────────────────────────────────────
    "www.booking.com": SiteOverride(
        name="Booking.com",
        domains=["www.booking.com", "booking.com"],
        requires_proxy=True,
        recommended_proxy="brightdata-unblock",
        preserve_cookies=True,
        # Booking.com uses Cloudflare + their own impression_UUID tracking
        extra_headers={
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "sec-fetch-dest": "document",
            "sec-fetch-mode": "navigate",
            "sec-fetch-site": "none",
            "sec-fetch-user": "?1",
            "upgrade-insecure-requests": "1",
            # Booking uses akamai for edge routing
            "Referer": "https://www.google.com/",
        },
        post_nav_delay=3.0,  # Booking has heavy JS that needs time
        # Inject fake Booking.com cookies that track session depth
        seed_cookies={
            "bkng": "11",  # booking.com cookie indicating active session
            "landing_page": "www.booking.com",
        },
        strategy_note=(
            "Booking.com uses impression_UUID generated per session. "
            "brightdata-unblock handles the Cloudflare layer. "
            "Booking.com tracks user behavior — add random delays between actions. "
            "DO NOT search too quickly — add 1-2s delays between search steps."
        ),
        notes="impression_UUID in cookies. akamai bot management. Heavy JS rendering.",
    ),

    # ── Expedia ─────────────────────────────────────────────────────────────────
    "www.expedia.com": SiteOverride(
        name="Expedia",
        domains=["www.expedia.com", "expedia.com"],
        requires_proxy=True,
        recommended_proxy="brightdata-unblock",
        preserve_cookies=True,
        # Expedia uses akamai bot management + their own JS fingerprinting
        extra_headers={
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "sec-fetch-dest": "document",
            "sec-fetch-mode": "navigate",
            "sec-fetch-site": "none",
            "sec-fetch-user": "?1",
            "upgrade-insecure-requests": "1",
            # Expedia checks for Correlation-ID header
            "Referer": "https://www.google.com/",
        },
        post_nav_delay=2.5,
        # Expedia detects via WebGL vendor string + canvas
        post_nav_js="""
            (function() {
                // Expedia checks navigator.connection (not available in headless)
                if (navigator.connection) {
                    Object.defineProperty(navigator, 'connection', {
                        value: {
                            effectiveType: '4g',
                            rtt: 50,
                            downlink: 10,
                            saveData: false
                        },
                        writable: true
                    });
                }
            })();
        """,
        strategy_note=(
            "Expedia uses akamai bot management. Use brightdata-unblock. "
            "Site is heavy JS — wait for post_nav_delay before taking actions. "
            "Expedia also checks for哑 mid-session behavior changes."
        ),
        notes="Akamai bot management. Heavy JS. WebGL + canvas fingerprinting.",
    ),

    # ── LinkedIn ────────────────────────────────────────────────────────────────
    "www.linkedin.com": SiteOverride(
        name="LinkedIn",
        domains=["www.linkedin.com", "linkedin.com"],
        requires_proxy=True,
        recommended_proxy="brightdata-unblock",
        preserve_cookies=True,
        # LinkedIn uses their own anti-bot + Cloudflare
        extra_headers={
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "sec-fetch-dest": "document",
            "sec-fetch-mode": "navigate",
            "sec-fetch-site": "none",
            "sec-fetch-user": "?1",
            "upgrade-insecure-requests": "1",
            "x-li-lang": "en_US",
            "x-restli-protocol-version": "2.0.0",
        },
        post_nav_delay=3.0,
        # LinkedIn checks for the li_* cookies
        seed_cookies={
            "li_at": "placeholder",  # Will be filled by login flow
            "JSESSIONID": "placeholder",
        },
        strategy_note=(
            "LinkedIn requires authentication — use credential vault to store "
            "li_at session cookie. Use brightdata-unblock. "
            "DO NOT crawl LinkedIn without login — bot detection is aggressive."
        ),
        notes="Requires login. Bot detection triggers on rapid scrolling.",
    ),

    # ── Amazon ─────────────────────────────────────────────────────────────────
    "www.amazon.com": SiteOverride(
        name="Amazon",
        domains=["www.amazon.com", "amazon.com"],
        requires_proxy=False,  # Amazon doesn't aggressively block
        recommended_proxy="brightdata",
        preserve_cookies=True,
        extra_headers={
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "sec-fetch-dest": "document",
            "sec-fetch-mode": "navigate",
            "sec-fetch-site": "none",
            "sec-fetch-user": "?1",
            "upgrade-insecure-requests": "1",
            # Amazon checks for x-main header
            "Referer": "https://www.google.com/",
        },
        post_nav_delay=1.5,
        strategy_note=(
            "Amazon mostly works without proxy. Bot detection triggers on "
            "rapid price checks and ASIN scraping. Add 2-3s delays between page loads."
        ),
        notes="Session cookie needed for cart. Captchas on repeated queries.",
    ),

    # ── Google (for warm-up) ────────────────────────────────────────────────────
    "www.google.com": SiteOverride(
        name="Google",
        domains=["www.google.com", "google.com"],
        requires_proxy=False,
        recommended_proxy="generic",
        preserve_cookies=False,
        extra_headers={
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        },
        post_nav_delay=0.5,
        pre_nav_delay=0.3,
        strategy_note="Use for warm-up only (visit google.com first before target site). Google sets gclid cookies that make subsequent sites look more organic.",
        notes="Good for warm-up. Google Search uses reCAPTCHA on rapid queries.",
    ),

    # ── Workable ───────────────────────────────────────────────────────────────
    "apply.workable.com": SiteOverride(
        name="Workable",
        domains=["apply.workable.com", "www.workable.com"],
        requires_proxy=True,
        recommended_proxy="brightdata-unblock",
        preserve_cookies=False,
        extra_headers={
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "sec-fetch-dest": "document",
            "sec-fetch-mode": "navigate",
            "sec-fetch-site": "same-site",
        },
        post_nav_delay=2.0,
        strategy_note="Workable uses DataDome for bot protection. Use brightdata-unblock proxy.",
        notes="DataDome protection on job application forms.",
    ),

    # ── Glassdoor ──────────────────────────────────────────────────────────────
    "www.glassdoor.com": SiteOverride(
        name="Glassdoor",
        domains=["www.glassdoor.com", "glassdoor.com"],
        requires_proxy=True,
        recommended_proxy="brightdata-unblock",
        preserve_cookies=True,
        extra_headers={
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "sec-fetch-dest": "document",
            "sec-fetch-mode": "navigate",
            "sec-fetch-site": "none",
            "sec-fetch-user": "?1",
        },
        post_nav_delay=2.0,
        strategy_note="Glassdoor uses DataDome. Use brightdata-unblock. Requires account for full access.",
        notes="DataDome on job listing pages.",
    ),
}


def match_domain(hostname: str) -> Optional[SiteOverride]:
    """
    Find a site override for the given hostname.

    Matches exact domain first, then parent domain (www.example.com → example.com).
    """
    # Exact match
    if hostname in SITE_OVERRIDES:
        return SITE_OVERRIDES[hostname]

    # Strip leading www.
    stripped = hostname
    if stripped.startswith("www."):
        stripped = stripped[4:]

    # Try stripped domain
    if stripped in SITE_OVERRIDES:
        return SITE_OVERRIDES[stripped]

    # Try parent domains (for subdomains like apply.workable.com)
    parts = stripped.split(".")
    if len(parts) >= 2:
        parent = ".".join(parts[-2:])
        if parent in SITE_OVERRIDES:
            return SITE_OVERRIDES[parent]

    return None


async def apply_site_override(page, override: SiteOverride) -> bool:
    """
    Apply a SiteOverride to a Playwright page.

    Steps:
    1. Set extra HTTP headers
    2. Set seed cookies (if any)
    3. Pre-nav JS (if any)
    4. Pre-nav delay (if any)

    Call this BEFORE page.goto().
    """
    import asyncio
    from urllib.parse import urlparse

    applied = []

    # 1. Extra headers
    if override.extra_headers:
        await page.set_extra_http_headers(override.extra_headers)
        applied.append(f"extra_headers ({len(override.extra_headers)} headers)")

    # 2. Seed cookies
    if override.seed_cookies:
        # Build cookie list
        current_url = page.url
        parsed = urlparse(current_url) if current_url else urlparse("https://example.com")
        domain = override.domains[0] if override.domains else parsed.netloc

        cookies = [
            {
                "name": name,
                "value": value,
                "domain": domain,
                "path": "/",
            }
            for name, value in override.seed_cookies.items()
        ]
        await page.context.set_cookies(cookies)
        applied.append(f"seed_cookies ({len(override.seed_cookies)} cookies)")

    # 3. Pre-nav JS
    if override.pre_nav_js:
        await page.evaluate(override.pre_nav_js)
        applied.append("pre_nav_js")

    # 4. Pre-nav delay
    if override.pre_nav_delay > 0:
        await asyncio.sleep(override.pre_nav_delay)
        applied.append(f"pre_nav_delay ({override.pre_nav_delay}s)")

    if applied:
        return True
    return False


def get_override_for_url(url: str) -> Optional[SiteOverride]:
    """Convenience: get the override for a URL string."""
    from urllib.parse import urlparse
    parsed = urlparse(url)
    return match_domain(parsed.netloc)
