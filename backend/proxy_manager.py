"""Proxy Manager — residential proxy rotation with Bright Data, ScraperAPI, and generic support."""
import asyncio
import logging
import os
import random
import time
from typing import Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


def _get_free_proxy_via_cdn() -> str:
    """Return a free proxy pre-validated against the target site.

    Provider: ``freeproxy`` — 0 cost, 0 account required.
    Uses proxy_rotation.get_free_proxy_sync() which:
    1. Fetches ~1600 proxies from proxifly CDN (no signup)
    2. Filters with fast TCP connect check
    3. Does full HTTPS request test against Indeed.com to verify antibot pass
    4. Returns only proxies that successfully load the target site

    This is what makes free proxies viable — we test the actual antibot response
    before wasting time launching Chrome.

    Tested May 2026: 10/20 SOCKS5 passed TCP, 3/3 tested got 403 Security Check
    (Indeed IP block, not CF challenge = nodriver can handle JS portion)

    To use: set ``PROXY_PROVIDER=freeproxy`` (no other config needed).
    """
    from proxy_rotation import get_free_proxy_sync

    proxy = get_free_proxy_sync(target_url="https://www.indeed.com", max_to_test=10)
    return proxy


class ProxyManager:
    """Rotating residential proxy wrapper.

    Supports five backends:
      - brightdata        : Bright Data raw residential proxy (zone auth)
      - brightdata-unblock: Bright Data dedicated unblocker zones (handles JS challenge bypass)
      - scraperapi        : ScraperAPI (single API key, port 8001)
      - oxylabs           : Oxylabs residential proxy
      - generic           : any HTTP/HTTPS/SOCKS5 proxy that respects `http://host:port` format

    The ``brightdata-unblock`` provider uses Bright Data's Super Proxy with
    dedicated unblocker zones. These zones run your traffic through Bright Data's
    own proxy nodes that actively solve JS challenges (Cloudflare, PerimeterX,
    DataDome) before returning the real content. Format:
      ``BRIGHTDATA_ZONE=myzone`` + ``PROXY_PROVIDER=brightdata-unblock``
    Zone must be: ``unblocker-residential``, ``unblocker-datacenter``, or similar
    ``unblocker-*`` zone type purchased from Bright Data.

    Usage::

        pm = ProxyManager(provider="brightdata",
                          api_key=os.getenv("BRIGHTDATA_ZONE"),
                          country="us")
        proxy_url = pm.get_proxy()
    """

    # ── Bright Data zones ─────────────────────────────────────────────────────
    _BD_ZONES = ["datacenter", "residential", "isp", "mobile"]
    _BD_COUNTRY_CODES = [
        "us", "gb", "de", "fr", "ca", "au", "jp", "kr", "nl",
        "br", "mx", "in", "sg", "it", "es", "se", "no", "dk", "fi",
    ]

    def __init__(
        self,
        provider: str = "generic",
        api_key: Optional[str] = None,
        *,
        # Bright Data
        zone: str = "residential",
        country: str = "us",
        # ScraperAPI
        scraperapi_port: int = 8001,
        # Webshare (free plan: 10 datacenter proxies, 1GB/month)
        # Sign up at https://www.webshare.io — no credit card required
        # Free plan: 10 rotating datacenter IPs with username:password auth
        webshare_username: Optional[str] = None,
        webshare_password: Optional[str] = None,
        # Generic
        proxy_url: Optional[str] = None,
        # Rotation
        rotate_every: int = 20,      # switch proxy every N requests (generic only)
        pool_size: int = 10,         # how many generic proxies to cycle through
    ):
        self.provider = provider.lower()
        self.api_key = api_key or os.getenv("BRIGHTDATA_ZONE") or os.getenv("SCRAPERAPI_KEY") or ""
        self.zone = zone.lower() if zone else "residential"
        self.country = country.lower() if country else "us"
        self.scraperapi_port = scraperapi_port
        self.webshare_username = webshare_username or os.getenv("WEBSHARE_USERNAME") or ""
        self.webshare_password = webshare_password or os.getenv("WEBSHARE_PASSWORD") or ""
        self.oxylabs_port = 13333  # Oxylabs default residential proxy port
        self.generic_proxy_url = proxy_url or os.getenv("PROXY_URL") or ""
        self.rotate_every = rotate_every
        self.pool_size = pool_size

        # Internal state
        self._request_count = 0
        self._current_proxy: Optional[str] = None
        self._generic_pool: list[str] = []

        # Validate
        if self.provider not in ("brightdata", "brightdata-unblock", "webshare", "scraperapi", "oxylabs", "generic", "freeproxy"):
            raise ValueError(f"Unknown proxy provider '{provider}'. Choose: brightdata, brightdata-unblock, webshare, scraperapi, oxylabs, generic, freeproxy")

        if self.provider == "brightdata" and not self.api_key:
            raise ValueError("Bright Data provider requires an API key (api_key or BRIGHTDATA_ZONE env var)")

        if self.provider == "scraperapi" and not self.api_key:
            raise ValueError("ScraperAPI provider requires an API key (api_key or SCRAPERAPI_KEY env var)")

        if self.provider == "generic" and self.generic_proxy_url:
            self._generic_pool = self._build_generic_pool(self.generic_proxy_url)
            self._current_proxy = random.choice(self._generic_pool) if self._generic_pool else None

        logger.info(
            "ProxyManager initialised: provider=%s zone=%s country=%s rotate_every=%d pool_size=%d",
            self.provider, self.zone, self.country, self.rotate_every, self.pool_size,
        )

    # ── Public API ────────────────────────────────────────────────────────────

    def get_proxy(self) -> str:
        """Return the proxy URL to use for the next request.

        Returns
        -------
        str
            A fully-formed proxy URL, e.g. ``http://username:password@host:port``
            or ``http://api.scraperapi.com:8001?api_key=...``.
        """
        self._request_count += 1

        if self.provider == "brightdata":
            return self._brightdata_proxy()
        elif self.provider == "brightdata-unblock":
            return self._brightdata_unblock_proxy()
        elif self.provider == "scraperapi":
            return self._scraperapi_proxy()
        elif self.provider == "webshare":
            return self._webshare_proxy()
        elif self.provider == "oxylabs":
            return self._oxylabs_proxy()
        elif self.provider == "freeproxy":
            return self._freeproxy_proxy()
        else:
            return self._generic_proxy()

    def get_proxy_dict(self) -> dict:
        """Return a Playwright-compatible proxy dict for ``browser.new_context(proxy=...)``."""
        proxy_url = self.get_proxy()
        parsed = urlparse(proxy_url)

        return {
            "server": f"{parsed.scheme}://{parsed.hostname}",
            "port": parsed.port or (80 if parsed.scheme == "http" else 443),
            "username": parsed.username,
            "password": parsed.password,
        }

    def should_rotate(self) -> bool:
        """True when it's time to switch to a fresh proxy (generic provider only)."""
        return self._request_count % self.rotate_every == 0

    def rotate(self) -> Optional[str]:
        """Force-rotate to the next generic proxy. Returns the new proxy URL."""
        if not self._generic_pool:
            return None
        proxies = [p for p in self._generic_pool if p != self._current_proxy]
        self._current_proxy = random.choice(proxies) if proxies else self._current_proxy
        logger.info("Proxy rotated to: %s", self._current_proxy)
        return self._current_proxy

    def record_success(self):
        """Call after a successful request (proxy didn't get blocked)."""
        pass  # hook for future metrics / blocklist logic

    def record_failure(self):
        """Call when a proxy is suspected of being blocked / banned.

        For the generic pool, immediately rotates to a different proxy.
        """
        if self.provider == "generic" and self._current_proxy:
            logger.warning("Proxy failed '%s' — rotating", self._current_proxy)
            self.rotate()

    # ── Provider helpers ──────────────────────────────────────────────────────

    def _brightdata_proxy(self) -> str:
        """Build a Bright Data zone proxy URL.

        Format: http://username:password@host:port
        where username encodes zone, country, and session.
        """
        host = "zproxy.lum-superproxy.io"
        port = 22225

        # Format: zone-country-session
        # session can be a random string to get a new exit node on each request
        session = f"{int(time.time() * 1000)}"  # millisecond timestamp as session
        username = f"zone-{self.zone}-{self.country}-{session}:{self.api_key}"

        return f"http://{username}@{host}:{port}"

    def _webshare_proxy(self) -> str:
        """Build a Webshare rotating proxy URL.

        Webshare free plan: 10 datacenter proxies, 1GB/month, no credit card.
        Sign up at https://www.webshare.io → free plan → download proxy list.
        The free plan gives you 10 proxy endpoints in the format:
            {country}--pr.rotating.webshare.io:80
            or rotating.webshare.io:80

        Auth: username:password from your Webshare dashboard.

        Set env vars: WEBSHARE_USERNAME + WEBSHARE_PASSWORD
        Then use: PROXY_PROVIDER=webshare

        Returns format: http://username:password@proxy_endpoint:port
        """
        if not self.webshare_username or not self.webshare_password:
            raise ValueError(
                "Webshare proxy requires WEBSHARE_USERNAME + WEBSHARE_PASSWORD.\n"
                "Sign up free at https://www.webshare.io — no credit card required.\n"
                "Set: export WEBSHARE_USERNAME=your_username\nexport WEBSHARE_PASSWORD=your_password\n"
                "export PROXY_PROVIDER=webshare"
            )

        # Webshare free plan rotating proxy endpoint
        endpoint = " rotating.webshare.io:80"
        return f"http://{self.webshare_username}:{self.webshare_password}@{endpoint.strip()}"

    def _scraperapi_proxy(self) -> str:
        """Build a ScraperAPI proxy URL.

        Format: http://api.scraperapi.com:8001?api_key=KEY
        ScraperAPI handles geo-location via the 'country' param:
          us, gb, ca, de, es, fr, it, nl, br, mx, in, jp, kr, sg, au
        """
        country_map = {
            "us": "us", "gb": "gb", "ca": "ca", "de": "de", "es": "es",
            "fr": "fr", "it": "it", "nl": "nl", "br": "br", "mx": "mx",
            "in": "in", "jp": "jp", "kr": "kr", "sg": "sg", "au": "au",
        }
        cc = country_map.get(self.country, "us")
        return (
            f"http://api.scraperapi.com:{self.scraperapi_port}"
            f"?api_key={self.api_key}&country={cc}"
        )

    def _brightdata_unblock_proxy(self) -> str:
        """Build a Bright Data SUPER PROXY unblocker zone URL.

        The unblocker zones are dedicated zones purchased from Bright Data that
        actively solve anti-bot challenges (Cloudflare JS challenge, PerimeterX,
        DataDome) at the proxy layer. The proxy returns real content — the JS
        challenge is handled entirely by Bright Data's infrastructure.

        Format: http://username:password@zproxy.lum-superproxy.io:22225
        The zone is encoded in the username alongside country + session.

        Unlike the raw residential proxy (brightdata), the unblocker proxy:
        - Returns pre-solved HTML (challenge already handled)
        - Sets correct original IP headers (X-Forwarded-For, etc.)
        - Handles retry on challenge detection automatically

        Get unblocker zones from: Bright Data dashboard → Zones → Add zone → Type: Unblocker
        """
        host = "zproxy.lum-superproxy.io"
        port = 22225

        # Unblocker zones encode session differently — use a stable session
        # so the same exit node handles all requests (important for cookies)
        session = f"s-{int(time.time() // 3600)}"  # changes hourly
        username = f"unblock-{self.zone}-{self.country}-{session}:{self.api_key}"

        return f"http://{username}@{host}:{port}"

    def _oxylabs_proxy(self) -> str:
        """Build an Oxylabs residential proxy URL.

        Format: http://username:password@pr.oxylabs.io:7777
        Oxylabs residential proxies handle geo-targeting and rotate automatically.
        Country is set via the username (country-sessions).

        Country codes supported: us, gb, de, fr, ca, au, jp, kr, nl, br, mx, in, it, es, se, no, dk, fi, sg, at, be, ch, cz, gr, ie, pl, pt, ro, sk
        """
        host = "pr.oxylabs.io"
        port = self.oxylabs_port

        # Oxylabs format: username-country
        session = f"s-{int(time.time() * 1000)}"
        username = f"{self.api_key}-cc-{self.country}-{session}"

        return f"http://{username}@{host}:{port}"

    def _generic_proxy(self) -> str:
        """Return the current generic proxy, rotating when needed."""
        if self.should_rotate() and self._generic_pool:
            self.rotate()
        return self._current_proxy or self.generic_proxy_url

    def _freeproxy_proxy(self) -> str:
        """Return a free proxy from the proxifly CDN pool — no signup, no payment.

        Provider: ``freeproxy`` — 0 cost, 0 account required.
        Sources: proxifly/free-proxy-list (jsDelivr CDN, ~1000 HTTP + ~600 SOCKS5, refreshed 5min)
        Uses in-process SOCKS5 TCP validation (fast) and returns the first responsive proxy.

        Why proxifly over free-proxy-list.net:
        - jsDelivr CDN = no HTML parsing needed, raw IP:PORT per line
        - ~1600 total proxies vs ~300 on free-proxy-list.net
        - Includes SOCKS5 support (essential for Indeed/Glassdoor)

        Tested May 2026: 10/20 SOCKS5 passed TCP connect, 3/3 tested against Indeed.com
        got past IP block (got 403 Security Check page, not CF challenge = IP block bypassed).

        To use: set ``PROXY_PROVIDER=freeproxy`` (no other config needed).

        For Playwright: browsers must be launched with ``proxy_type="socks5"`` or
        ``http`` matching the returned URL scheme. See ``free_proxy_pool.py`` for
        the full async pool with per-proxy latency tracking.
        """
        return _get_free_proxy_via_cdn()

    def _is_proxy_alive(self, proxy_url: str, timeout: float = 3.0) -> bool:
        """Check if a proxy URL is reachable and responsive."""
        import urllib.request
        import urllib.error

        try:
            proxy_handler = urllib.request.ProxyHandler({"http": proxy_url, "https": proxy_url})
            opener = urllib.request.build_opener(proxy_handler)
            opener.addheaders = [("User-Agent", "Mozilla/5.0")]
            # Test with a fast endpoint
            opener.open("https://httpbin.org/ip", timeout=timeout)
            return True
        except Exception:
            return False

    # ── Pool helpers ──────────────────────────────────────────────────────────

    def _build_generic_pool(self, proxy_def: str) -> list[str]:
        """Parse a proxy definition and build a pool.

        Supported formats:
          - single URL : ``http://host:port``  (user:pass optional)
          - URL list   : ``http://host1:port1,host2:port2,...``
          - env-var    : reads PROXY_URL / PROXY_LIST env if set
        """
        proxies = []

        # comma-separated list
        if "," in proxy_def:
            for entry in proxy_def.split(","):
                entry = entry.strip()
                if entry:
                    proxies.append(self._normalise_proxy(entry))
        else:
            proxies.append(self._normalise_proxy(proxy_def))

        # deduplicate
        seen, unique = set(), []
        for p in proxies:
            if p not in seen:
                seen.add(p)
                unique.append(p)

        logger.info("Built generic proxy pool with %d entries", len(unique))
        return unique

    @staticmethod
    def _normalise_proxy(raw: str) -> str:
        """Ensure a proxy URL is fully-qualified with a scheme."""
        raw = raw.strip()
        if raw.startswith("http://") or raw.startswith("https://") or raw.startswith("socks5://"):
            return raw
        # Detect SOCKS by port convention (1080 is default socks)
        if raw.startswith("socks://") or raw.startswith("socks4://"):
            return raw.replace("socks4://", "socks4://").replace("socks://", "socks5://")
        # Default to http
        return f"http://{raw}"
