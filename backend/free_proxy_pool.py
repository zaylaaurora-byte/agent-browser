"""
free_proxy_pool.py — T043: Zero-cost rotating proxy pool

Sources (no signup required):
- https://cdn.jsdelivr.net/gh/proxifly/free-proxy-list@main/proxies/protocols/http/data.txt
  → ~1000+ HTTP proxies, refreshed every 5 min
- https://cdn.jsdelivr.net/gh/proxifly/free-proxy-list@main/proxies/protocols/socks5/data.txt
  → ~600+ SOCKS5 proxies

No API key, no account, no credit card.

Usage:
  from free_proxy_pool import FreeProxyPool
  pool = FreeProxyPool()
  proxy = pool.get_random()       # str like "http://ip:port"
  pool.mark_dead(proxy)           # removes from pool
  pool.get_all()                  # list of all working proxies

  # Use with BrowserAgent:
  agent = BrowserAgent(proxy_provider="generic", proxy_url=pool.get_random())
"""

import asyncio
import random
import time
import urllib.request
import urllib.error
import urllib.parse
import ipaddress
import re
import logging
from typing import Optional
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

logger = logging.getLogger("free_proxy_pool")

# ─── Sources ────────────────────────────────────────────────────────────────

PROXIFLY_HTTP = "https://cdn.jsdelivr.net/gh/proxifly/free-proxy-list@main/proxies/protocols/http/data.txt"
PROXIFLY_SOCKS5 = "https://cdn.jsdelivr.net/gh/proxifly/free-proxy-list@main/proxies/protocols/socks5/data.txt"
PROXIFLY_SOCKS4 = "https://cdn.jsdelivr.net/gh/proxifly/free-proxy-list@main/proxies/protocols/socks4/data.txt"
PROXIFLY_ALL = "https://cdn.jsdelivr.net/gh/proxifly/free-proxy-list@main/proxies/all/data.txt"

# Backup sources (no JS / no signup required)
BACKUP_SOURCES = [
    "https://www.proxyrack.com/free-proxy-list/",
]

# ─── Validation ──────────────────────────────────────────────────────────────

TIMEOUT = 5          # seconds to test each proxy
MAX_RETRIES = 2     # retries before accepting a proxy
MIN_SUCCESS_RATE = 0.5  # proxy must pass this many checks to be kept
TARGET_POOL_SIZE = 50   # minimum working proxies to maintain


@dataclass
class ProxyEntry:
    url: str                    # "http://ip:port" or "socks5://ip:port"
    ip: str
    port: int
    protocol: str               # "http", "socks5", "socks4"
    country: Optional[str] = None
    latency_ms: float = 0.0
    success_count: int = 0
    fail_count: int = 0
    last_tested: float = field(default_factory=time.time)
    is_free: bool = True

    @property
    def is_working(self) -> bool:
        total = self.success_count + self.fail_count
        if total == 0:
            return True  # untested = assume working
        return (self.success_count / total) >= MIN_SUCCESS_RATE


class FreeProxyPool:
    """Free proxy pool fetched from proxifly (jsDelivr CDN). No auth required."""

    def __init__(
        self,
        pool_dir: str = "~/.agent-browser/proxy_pools",
        target_size: int = TARGET_POOL_SIZE,
        timeout: int = TIMEOUT,
        max_workers: int = 20,
    ):
        self.pool_dir = Path(pool_dir).expanduser()
        self.pool_dir.mkdir(parents=True, exist_ok=True)
        self.target_size = target_size
        self.timeout = timeout
        self.max_workers = max_workers
        self._pool: list[ProxyEntry] = []
        self._lock = asyncio.Lock()
        self._persist_path = self.pool_dir / "working_proxies.txt"
        self._load_cache()

    # ── Public API ────────────────────────────────────────────────────────────

    def get_random(self) -> Optional[str]:
        """Return a random working proxy URL, or None if pool is empty."""
        working = [p for p in self._pool if p.is_working]
        if not working:
            return None
        return random.choice(working).url

    def get_for_country(self, country: str) -> Optional[str]:
        """Return a random working proxy from a specific country (e.g. 'US')."""
        candidates = [
            p for p in self._pool
            if p.is_working and p.country and p.country.upper() == country.upper()
        ]
        if not candidates:
            return None
        return random.choice(candidates).url

    def get_all(self) -> list[str]:
        """Return all working proxy URLs."""
        return [p.url for p in self._pool if p.is_working]

    def mark_dead(self, proxy_url: str) -> None:
        """Mark a proxy as failed."""
        for p in self._pool:
            if p.url == proxy_url:
                p.fail_count += 1
                logger.debug(f"marked dead: {proxy_url} ({p.fail_count} fails)")
                break
        self._save_cache()

    def mark_live(self, proxy_url: str) -> None:
        """Mark a proxy as successful."""
        for p in self._pool:
            if p.url == proxy_url:
                p.success_count += 1
                p.last_tested = time.time()
                break
        self._save_cache()

    def count(self) -> int:
        return len([p for p in self._pool if p.is_working])

    # ── Fetching ──────────────────────────────────────────────────────────────

    async def refresh(self, force: bool = False) -> list[ProxyEntry]:
        """Fetch fresh proxies from all sources, validate in parallel, return working ones."""
        async with self._lock:
            raw = await self._fetch_all_sources()
            raw_proxies = self._parse_proxies(raw)
            logger.info(f"fetched {len(raw_proxies)} raw proxies from sources")

            if not raw_proxies and not force:
                # Return existing pool if fetch failed
                return [p for p in self._pool if p.is_working]

            # Validate in parallel
            validated = await self._validate_batch(raw_proxies)
            logger.info(f"{len(validated)}/{len(raw_proxies)} proxies passed validation")

            # Merge with existing pool
            self._merge_pool(validated)
            self._save_cache()

            return [p for p in self._pool if p.is_working]

    async def _fetch_all_sources(self) -> list[str]:
        """Fetch raw proxy lists from all sources concurrently."""
        sources = [PROXIFLY_HTTP, PROXIFLY_SOCKS5, PROXIFLY_SOCKS4]
        results: list[str] = []

        async def fetch_one(url: str) -> str:
            try:
                async with asyncio.timeout(15):
                    data = await asyncio.get_event_loop().run_in_executor(
                        None,
                        lambda: urllib.request.urlopen(url, timeout=15).read().decode()
                    )
                    return data
            except Exception as e:
                logger.warning(f"fetch failed: {url} → {e}")
                return ""

        fetched = await asyncio.gather(*[fetch_one(s) for s in sources])
        for data in fetched:
            if data:
                results.append(data)

        return results

    def _parse_proxies(self, raw_data: list[str]) -> list[ProxyEntry]:
        """Parse raw text data into ProxyEntry objects."""
        entries: list[ProxyEntry] = []
        seen: set[str] = set()

        ip_port_re = re.compile(r"(\d+\.\d+\.\d+\.\d+):(\d+)")

        for text in raw_data:
            for line in text.splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue

                # Try IP:PORT format
                match = ip_port_re.search(line)
                if not match:
                    # Try as full URL
                    try:
                        parsed = urllib.parse.urlparse(line)
                        if parsed.hostname and parsed.port:
                            ip, port = parsed.hostname, parsed.port
                        else:
                            continue
                    except Exception:
                        continue
                else:
                    ip, port = match.group(1), int(match.group(2))

                key = f"{ip}:{port}"
                if key in seen:
                    continue
                seen.add(key)

                # Determine protocol from URL or line context
                if "socks5" in line.lower() or line.startswith("socks5://"):
                    protocol = "socks5"
                elif "socks4" in line.lower() or line.startswith("socks4://"):
                    protocol = "socks4"
                elif "socks" in line.lower():
                    protocol = "socks5"  # default
                else:
                    protocol = "http"

                # Try to extract country from line
                country = self._extract_country(line)

                url = f"http://{ip}:{port}" if protocol == "http" else f"{protocol}://{ip}:{port}"

                entries.append(ProxyEntry(
                    url=url,
                    ip=ip,
                    port=port,
                    protocol=protocol,
                    country=country,
                ))

        return entries

    def _extract_country(self, line: str) -> Optional[str]:
        """Try to extract country code from proxy line."""
        # Common format: "IP:PORT COUNTRY" or "IP:PORT,country"
        parts = line.split()
        if len(parts) >= 2:
            last = parts[-1].upper()
            if len(last) == 2 and last.isalpha():
                return last
        return None

    # ── Validation ────────────────────────────────────────────────────────────

    async def _validate_batch(self, entries: list[ProxyEntry]) -> list[ProxyEntry]:
        """Test proxies in parallel. Returns only those that successfully connect."""
        semaphore = asyncio.Semaphore(self.max_workers)

        async def validate_one(entry: ProxyEntry) -> Optional[ProxyEntry]:
            async with semaphore:
                loop = asyncio.get_event_loop()
                try:
                    # Use httpbin.org/ip as the test endpoint
                    proxy_url = entry.url
                    result = await loop.run_in_executor(
                        None,
                        self._test_proxy_sync,
                        proxy_url,
                    )
                    if result:
                        entry.latency_ms = result
                        entry.success_count = 1
                        return entry
                    else:
                        return None
                except Exception:
                    return None

        results = await asyncio.gather(*[validate_one(e) for e in entries])
        return [r for r in results if r is not None]

    def _test_proxy_sync(self, proxy_url: str, test_url: str = "https://httpbin.org/ip") -> Optional[float]:
        """Test a single proxy synchronously. Returns latency in ms or None if failed."""
        import socket
        start = time.time()
        try:
            proxy_handler = urllib.request.ProxyHandler({
                "http": proxy_url,
                "https": proxy_url,
            })
            opener = urllib.request.build_opener(proxy_handler)
            opener.addheaders = [
                ("User-Agent", "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36")
            ]
            opener.open(test_url, timeout=self.timeout)
            latency = (time.time() - start) * 1000
            return latency
        except Exception:
            return None

    # ── Persistence ───────────────────────────────────────────────────────────

    def _merge_pool(self, new_entries: list[ProxyEntry]) -> None:
        """Merge validated entries into the pool, keeping best scores for duplicates."""
        existing = {p.url: p for p in self._pool}
        for entry in new_entries:
            if entry.url in existing:
                # Keep the one with more tests
                old = existing[entry.url]
                old.success_count = max(old.success_count, entry.success_count)
                old.fail_count = min(old.fail_count, entry.fail_count)
                old.last_tested = time.time()
            else:
                self._pool.append(entry)

    def _save_cache(self) -> None:
        try:
            with open(self._persist_path, "w") as f:
                for p in self._pool:
                    f.write(
                        f"{p.url}|{p.protocol}|{p.country or ''}|{p.success_count}|{p.fail_count}\n"
                    )
        except Exception as e:
            logger.warning(f"save cache failed: {e}")

    def _load_cache(self) -> None:
        if not self._persist_path.exists():
            return
        try:
            with open(self._persist_path) as f:
                for line in f:
                    parts = line.strip().split("|")
                    if len(parts) >= 5:
                        url, protocol, country, sc, fc = parts[0], parts[1], parts[2], int(parts[3]), int(parts[4])
                        ip_port = url.split("://")[-1]
                        ip, port_s = ip_port.rsplit(":", 1)
                        self._pool.append(ProxyEntry(
                            url=url,
                            ip=ip,
                            port=int(port_s),
                            protocol=protocol,
                            country=country or None,
                            success_count=sc,
                            fail_count=fc,
                            last_tested=time.time(),
                        ))
            logger.info(f"loaded {len(self._pool)} cached proxies")
        except Exception as e:
            logger.warning(f"load cache failed: {e}")

    # ── CLI ───────────────────────────────────────────────────────────────────

    async def interactive_test(self, url: str, max_attempts: int = 10) -> bool:
        """Try up to max_attempts to reach target URL via different proxies."""
        print(f"[*] Testing {url} via free proxy pool ({self.count()} available)")
        for i in range(max_attempts):
            proxy = self.get_random()
            if not proxy:
                print("[!] Pool empty, refreshing...")
                await self.refresh(force=True)
                proxy = self.get_random()
                if not proxy:
                    print("[!] Still empty after refresh. Giving up.")
                    return False

            print(f"  [{i+1}/{max_attempts}] Trying {proxy}...", end=" ", flush=True)
            try:
                proxy_handler = urllib.request.ProxyHandler({
                    "http": proxy,
                    "https": proxy,
                })
                opener = urllib.request.build_opener(proxy_handler)
                opener.addheaders = [
                    ("User-Agent", "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36")
                ]
                response = opener.open(url, timeout=self.timeout + 5)
                status = response.getcode()
                print(f"✅ Status {status}")
                if status == 200:
                    return True
            except Exception as e:
                print(f"❌ {type(e).__name__}: {e}")
                self.mark_dead(proxy)

            await asyncio.sleep(1)

        print(f"[!] Failed all {max_attempts} attempts")
        return False


async def main():
    import argparse
    parser = argparse.ArgumentParser(description="Free rotating proxy pool")
    parser.add_argument("--test", type=str, help="URL to test connectivity")
    parser.add_argument("--refresh", action="store_true", help="Force refresh proxy list")
    parser.add_argument("--count", type=int, default=5, help="Max attempts")
    args = parser.parse_args()

    pool = FreeProxyPool()

    if args.refresh:
        print("[*] Refreshing proxy pool...")
        working = await pool.refresh(force=True)
        print(f"[+] {len(working)} working proxies")
        for p in working[:10]:
            print(f"  {p.url} ({p.latency_ms:.0f}ms)")

    if args.test:
        success = await pool.interactive_test(args.test, max_attempts=args.count)
        return 0 if success else 1

    # Default: show pool status
    print(f"[*] Pool: {pool.count()} working proxies")
    print(f"[*] Run --refresh to fetch new proxies")
    print(f"[*] Run --test https://example.com to test connectivity")
    return 0


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    sys.exit(asyncio.run(main()))
