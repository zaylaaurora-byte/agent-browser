"""
proxy_rotation.py — T043: Free proxy rotation with antibot pre-validation

Strategy:
1. Fetch proxy list from proxifly CDN (no signup)
2. Pre-validate each proxy against the target site (not just TCP connect)
3. Return only proxies that pass antibot check
4. Rotate through validated proxies

This is what makes the difference — a proxy can pass TCP but fail HTTPS antibot.
We test the actual HTTPS response to filter out CF-blocked IPs before launching Chrome.
"""

import asyncio
import logging
import random
import socket
import time
import urllib.request
import urllib.parse
from typing import Optional
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger("proxy_rotation")

PROXIFLY_HTTP = "https://cdn.jsdelivr.net/gh/proxifly/free-proxy-list@main/proxies/protocols/http/data.txt"
PROXIFLY_SOCKS5 = "https://cdn.jsdelivr.net/gh/proxifly/free-proxy-list@main/proxies/protocols/socks5/data.txt"
PROXY_TTL = 180       # proxy list cache (seconds)
MAX_VALIDATE_PARALLEL = 15  # concurrent proxy tests
CONNECT_TIMEOUT = 4   # TCP connect timeout
HTTP_TIMEOUT = 15     # HTTP request timeout


def _parse_proxy_entry(entry: str) -> Optional[tuple[str, str, int]]:
    """Parse a proxy entry. Returns (scheme, host, port) or None.

    Handles both formats:
      - Full URL: socks5://72.49.49.11:31034  or  http://103.174.236.88:8080
      - Raw IP:  72.49.49.11:31034
    """
    entry = entry.strip()
    if not entry or entry.startswith("#"):
        return None
    try:
        if "://" in entry:
            # Full URL format — scheme already embedded, don't re-add it
            parsed = urllib.parse.urlparse(entry)
            scheme = parsed.scheme
            host = parsed.hostname
            port = parsed.port
        else:
            # Raw IP:PORT format
            scheme = "http"
            host, port_s = entry.rsplit(":", 1)
            port = int(port_s)

        if not host or not port:
            return None
        return scheme, host, port
    except Exception:
        return None


async def fetch_proxy_list() -> list[str]:
    """Fetch raw proxy list from proxifly CDN."""
    loop = asyncio.get_event_loop()
    results: list[str] = []

    def _fetch_sync(url: str) -> str:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            data = urllib.request.urlopen(req, timeout=15).read().decode()
            return data
        except Exception as e:
            logger.warning(f"fetch {url}: {e}")
            return ""

    http_data, socks5_data = await asyncio.gather(
        loop.run_in_executor(None, lambda: _fetch_sync(PROXIFLY_HTTP)),
        loop.run_in_executor(None, lambda: _fetch_sync(PROXIFLY_SOCKS5)),
    )

    for data in (http_data, socks5_data):
        for line in data.splitlines():
            parsed = _parse_proxy_entry(line)
            if parsed:
                s, h, p = parsed
                results.append(f"{s}://{h}:{p}")

    # Deduplicate
    seen = set()
    deduped = []
    for p in results:
        if p not in seen:
            seen.add(p)
            deduped.append(p)
    return deduped


def _tcp_connect(host: str, port: int) -> bool:
    """Fast TCP connect check."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(CONNECT_TIMEOUT)
        sock.connect((host, port))
        sock.close()
        return True
    except Exception:
        return False


async def _validate_proxy_http(
    proxy_scheme: str,
    proxy_host: str,
    proxy_port: int,
    target_url: str = "https://www.indeed.com",
) -> tuple[bool, str]:
    """Test a single proxy via full HTTPS request. Returns (success, reason)."""
    loop = asyncio.get_event_loop()

    def _sync_test() -> tuple[bool, str]:
        try:
            import socks  # PySocks

            # Set up SOCKS5 proxy
            socks.set_default_proxy(socks.SOCKS5, proxy_host, proxy_port)
            sock = socks.socksocket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(HTTP_TIMEOUT)

            # Parse target
            parsed = urllib.parse.urlparse(target_url)
            hostname = parsed.hostname
            port = parsed.port or 443
            path = parsed.path or "/"

            # HTTPS connect
            ctx = ssl_context = __import__("ssl")._create_unverified_context()
            ssock = ctx.wrap_socket(sock, server_hostname=hostname)
            ssock.connect((hostname, port))

            # HTTP request
            req = (
                f"GET {path} HTTP/1.1\r\n"
                f"Host: {hostname}\r\n"
                f"User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36\r\n"
                f"Accept: text/html,application/xhtml+xml,application/xml;q=0.9\r\n"
                f"Accept-Language: en-US,en;q=0.9\r\n"
                f"Connection: close\r\n"
                f"\r\n"
            ).encode()

            ssock.sendall(req)

            # Read response (first 3000 bytes is enough)
            resp = b""
            while len(resp) < 3000:
                chunk = ssock.recv(4096)
                if not chunk:
                    break
                resp += chunk

            ssock.close()
            sock.close()

            text = resp.decode("utf-8", errors="ignore")
            he = text.find("\r\n\r\n")
            headers = text[:he] if he != -1 else ""
            body = text[he + 4 : he + 4 + 1000] if he != -1 else ""

            status_line = headers.splitlines()[0] if headers else "unknown"
            body_preview = body[:300]

            # Classify response
            lc_body = body.lower()
            if any(
                x in lc_body
                for x in [
                    "cloudflare",
                    "accessdenied",
                    "captcha",
                    "turnstile",
                    "checking your browser",
                ]
            ):
                return False, f"CF blocked ({status_line})"
            if any(x in lc_body for x in ["security check", "blocked - indeed"]):
                return False, f"Indeed blocked ({status_line})"
            if "indeed" in lc_body and len(body) > 200:
                return True, f"PASS ({status_line}, {len(body)} bytes)"
            if len(body) > 200:
                return True, f"Content loaded ({status_line}, {len(body)} bytes)"

            return False, f"Empty/unknown ({status_line})"

        except Exception as e:
            return False, f"{type(e).__name__}: {str(e)[:60]}"

    return await loop.run_in_executor(None, _sync_test)


async def get_validated_proxy(
    target_url: str = "https://www.indeed.com",
    max_to_test: int = 20,
    prefer_socks5: bool = True,
) -> Optional[str]:
    """Get a free proxy that passes antibot check for the target URL.

    Strategy:
    1. Fetch proxy list from proxifly CDN (prioritize SOCKS5)
    2. Do TCP connect check first (fast filter)
    3. For proxies passing TCP, do full HTTPS request test
    4. Return first proxy that loads the target site (not blocked)
    5. If all fail, return None (no free proxy works for this target)

    Args:
        target_url: URL to test antibot against
        max_to_test: Max proxies to validate before giving up
        prefer_socks5: If True, test SOCKS5 first (better for HTTPS)

    Returns:
        A validated proxy URL (e.g. "socks5://host:port") or None
    """
    logger.info(f"[proxy_rotation] Fetching proxy list for {target_url}...")
    raw_proxies = await fetch_proxy_list()
    logger.info(f"[proxy_rotation] Got {len(raw_proxies)} proxies from CDN")

    if not raw_proxies:
        return None

    # Shuffle for variety
    random.shuffle(raw_proxies)

    # Prioritize SOCKS5 (better for HTTPS tunneling)
    socks5 = [p for p in raw_proxies if "socks5" in p.lower()]
    http_proxies = [p for p in raw_proxies if "socks5" not in p.lower()]
    ordered = socks5 + http_proxies if prefer_socks5 else raw_proxies

    to_test = ordered[:max_to_test]
    logger.info(f"[proxy_rotation] Testing {len(to_test)} proxies...")

    # Phase 1: TCP connect check (fast)
    tcp_ok: list[tuple[str, str, int, str]] = []  # (full_url, host, port, scheme)

    for entry in to_test:
        parsed = _parse_proxy_entry(entry)
        if not parsed:
            continue
        scheme, host, port = parsed
        ok = await asyncio.get_event_loop().run_in_executor(
            None, lambda h=host, p=port: _tcp_connect(h, p)
        )
        if ok:
            tcp_ok.append((entry, host, port, scheme))
            logger.debug(f"  TCP OK: {entry}")

    logger.info(f"[proxy_rotation] {len(tcp_ok)}/{len(to_test)} passed TCP")

    if not tcp_ok:
        return None

    # Phase 2: Full HTTPS request test (antibot check)
    for full_url, host, port, scheme in tcp_ok:
        logger.info(f"[proxy_rotation] Testing HTTPS: {full_url}")
        ok, reason = await _validate_proxy_http(scheme, host, port, target_url)
        logger.info(f"[proxy_rotation]   → {reason}")
        if ok:
            logger.info(f"[proxy_rotation] ✅ VALIDATED: {full_url}")
            return full_url

    logger.warning(f"[proxy_rotation] ❌ All {len(tcp_ok)} TCP-OK proxies blocked by antibot")
    return None


# ─── Sync shortcut for use in ProxyManager (sync context) ─────────────────────

_proxy_cache: Optional[tuple[float, str]] = None  # (fetch_time, validated_proxy)


def get_free_proxy_sync(
    target_url: str = "https://www.indeed.com",
    max_to_test: int = 10,
) -> str:
    """Synchronous version — use this in ProxyManager.get_proxy().

    Caches the last validated proxy for 60 seconds to avoid repeated CDN fetches.
    On cache miss, runs the full async validation in a new event loop.
    """
    global _proxy_cache
    now = time.time()

    if _proxy_cache and (now - _proxy_cache[0]) < 60:
        return _proxy_cache[1]

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        proxy = loop.run_until_complete(
            get_validated_proxy(target_url, max_to_test=max_to_test)
        )
        loop.close()
    except Exception as e:
        logger.warning(f"[proxy_rotation] sync validation failed: {e}")
        proxy = None

    if proxy:
        _proxy_cache = (now, proxy)
    return proxy or ""


if __name__ == "__main__":
    # CLI test
    import sys

    async def main():
        target = sys.argv[1] if len(sys.argv) > 1 else "https://www.indeed.com"
        print(f"[*] Finding validated proxy for: {target}")
        proxy = await get_validated_proxy(target, max_to_test=20)
        if proxy:
            print(f"[+] VALIDATED PROXY: {proxy}")
            return 0
        else:
            print("[!] No working proxy found")
            return 1

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    import sys

    sys.exit(asyncio.run(main()))
