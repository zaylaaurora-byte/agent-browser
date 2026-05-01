"""Proxy Manager — residential proxy rotation with Bright Data, ScraperAPI, and generic support."""
import asyncio
import logging
import os
import random
import time
from typing import Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class ProxyManager:
    """Rotating residential proxy wrapper.

    Supports three backends:
      - brightdata  : Bright Data's residential proxy network (zone auth)
      - scraperapi  : ScraperAPI (single API key, port 8001)
      - generic     : any HTTP/HTTPS/SOCKS5 proxy that respects `http://host:port` format

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
        self.generic_proxy_url = proxy_url or os.getenv("PROXY_URL") or ""
        self.rotate_every = rotate_every
        self.pool_size = pool_size

        # Internal state
        self._request_count = 0
        self._current_proxy: Optional[str] = None
        self._generic_pool: list[str] = []

        # Validate
        if self.provider not in ("brightdata", "scraperapi", "generic"):
            raise ValueError(f"Unknown proxy provider '{provider}'. Choose: brightdata, scraperapi, generic")

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
        elif self.provider == "scraperapi":
            return self._scraperapi_proxy()
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

    def _generic_proxy(self) -> str:
        """Return the current generic proxy, rotating when needed."""
        if self.should_rotate() and self._generic_pool:
            self.rotate()
        return self._current_proxy or self.generic_proxy_url

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
