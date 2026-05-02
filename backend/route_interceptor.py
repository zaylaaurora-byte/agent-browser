"""
route_interceptor.py — T030: Request/response interception for anti-bot detection and bypass.

Implements Playwright route interception to:
1. Detect and handle anti-bot redirects (302/303 to challenge pages, 403 with challenge headers)
2. Identify fingerprinting headers in responses (CF-Ray, JA3 cookies, Bot management headers)
3. Automatically inject challenge bypass tokens when detected
4. Track per-domain challenge history to prioritize stealth on repeat visits

This is a CRITICAL layer: many sites don't block on the first request but instead
redirect to a JavaScript challenge on the 2nd or 3rd request after profiling the client.
Route interception lets us catch these mid-session and switch strategies.

Key patterns detected:
- Cloudflare: `cf-ray`, `cf-mitiged`, `__cf_challenge`, `cf-Captcha-Token`
- Akamai: `akamai-x-get-client-ip`, `akamai-x-cache`
- PerimeterX: `_px3`, `_pxCaptcha`, `X-PX`
- DataDome: `dd_z`, `dd_data`, `datadome`
- other anti-bots set challenge cookies + redirect chains

Strategy on detection:
1. If redirect to challenge URL: intercept, pause, inject delay, then replay
2. If 403 + challenge headers: retry with different TLS profile / browser engine
3. If captcha redirect: delegate to captcha_solver.py
4. If JS challenge: wait for challenge JS to execute, then retry
"""

import asyncio
import logging
import time
import re
from typing import Optional, Callable, Dict, Any, List
from urllib.parse import urlparse, parse_qs, urljoin
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class ChallengeType(Enum):
    NONE = "none"
    CLOUDFLARE_JS = "cloudflare_js"       # "Checking your browser..." page
    CLOUDFLARE_CHALLENGE = "cloudflare_challenge"  # cf challenge
    CAPTCHA = "captcha"                     # hCaptcha / reCAPTCHA
    AKAMAI = "akamai"                       # Akamai bot management
    PERIMETERX = "perimeterx"               # PerimeterX / ShadowD
    DATADOME = "datadome"                   # DataDome
    IMMUNEFILION = "immunefilion"           # Immunefilion
    CUSTOM_CHALLENGE = "custom"             # Generic JS challenge


@dataclass
class ChallengeInfo:
    challenge_type: ChallengeType = ChallengeType.NONE
    challenge_url: str = ""
    challenge_domain: str = ""
    challenge_cookie: str = ""
    challenge_header: str = ""
    redirect_chain: List[str] = field(default_factory=list)
    response_code: int = 0
    detected_at: float = 0
    bypass_attempts: int = 0


@dataclass
class RouteInterceptionResult:
    action: str  # "allow", "block", "retry", "bypass", "escalate"
    reason: str
    challenge: Optional[ChallengeInfo] = None
    retry_with_different_tier: bool = False
    headers_added: Optional[Dict[str, str]] = None
    cookies_set: Optional[Dict[str, str]] = None


# ── Anti-bot header/reponse signatures ─────────────────────────────────────────

CHALLENGE_PATTERNS = {
    ChallengeType.CLOUDFLARE_JS: {
        "url_patterns": [
            r"/.well-known/cloudflare-challenge",
            r"/cdn-cgi/challenge-platform",
            r"/__cf_client_verify",
        ],
        "header_patterns": {
            "cf-ray": r".+",
            "cf-mitiged": r".+",
        },
        "body_patterns": [
            r"Checking your browser",
            r"cloudflare",
            r"cf-challenge",
            r"ray id",
        ],
        "js_paths": [
            "/cdn-cgi/challenge-platform/*/orchestrate/*/v1",
            "/cdn-cgi/challenge-platform//*/b.*/orchestrate/*",
        ],
    },
    ChallengeType.CAPTCHA: {
        "url_patterns": [
            r"/generate_204",  # Google captcha trigger
            r"/safebrowsing",
        ],
        "header_patterns": {
            "cf-mitiged": r"captcha",
        },
        "body_patterns": [
            r"captcha",
            r"h-captcha",
            r"g-recaptcha",
            r"turnstile",
        ],
    },
    ChallengeType.AKAMAI: {
        "header_patterns": {
            "akamai-x-get-client-ip": r".+",
            "akamai-x-cache": r".+",
            "akamai-x-true-client-ip": r".+",
        },
        "body_patterns": [
            r"Reference.*AkamaiGHost",
            r"AkamaiGHost",
        ],
    },
    ChallengeType.PERIMETERX: {
        "cookie_patterns": [
            r"_px3=[a-f0-9]{32,}",
            r"_pxCaptcha=[^;]+",
        ],
        "header_patterns": {
            "x-px": r".+",
            "x-p-x": r".+",
        },
        "body_patterns": [
            r"perimeterx",
            r"PX.*challenge",
        ],
    },
    ChallengeType.DATADOME: {
        "cookie_patterns": [
            r"dd_z=[^;]+",
            r"dd_data=[^;]+",
            r"datadome=[^;]+",
        ],
        "body_patterns": [
            r"datadome",
            r"DD_Z",
        ],
    },
}


class RouteInterceptor:
    """
    Intercepts all browser requests/responses to detect and handle anti-bot challenges.

    Usage:
        interceptor = RouteInterceptor(agent)
        await interceptor.register(page)  # attaches route handlers

    The interceptor maintains per-domain state so that a site that challenges
    on the 2nd request is handled appropriately (retry with different profile, etc.).
    """

    def __init__(self, agent, on_challenge_callback: Optional[Callable] = None):
        self.agent = agent
        self.on_challenge_callback = on_challenge_callback  # called when challenge detected
        self._challenges: Dict[str, ChallengeInfo] = {}  # domain -> ChallengeInfo
        self._blocked_paths: Dict[str, int] = {}  # path pattern -> block_count
        self._route_handler_added = False
        self._total_interceptions = 0

    def _detect_challenge(
        self,
        url: str,
        response_headers: Dict[str, str],
        status: int,
        response_body: Optional[str] = None,
        request_cookies: Optional[Dict[str, str]] = None,
    ) -> ChallengeInfo:
        """
        Analyze a response to detect if it's a challenge/blocking page.
        Returns ChallengeInfo if detected, else ChallengeInfo with type NONE.
        """
        parsed = urlparse(url)
        domain = parsed.netloc
        body = response_body or ""
        body_lower = body.lower()

        # Normalize headers (lowercase keys)
        headers = {k.lower(): v for k, v in response_headers.items()}

        info = ChallengeInfo(
            response_code=status,
            detected_at=time.time(),
            challenge_domain=domain,
        )

        # ── Check by status code + challenge headers ────────────────────────────
        if status in (403, 429, 503):
            # 403/429/503 = likely blocked or challenge
            if "cf-ray" in headers or "cf-mitiged" in headers:
                info.challenge_type = ChallengeType.CLOUDFLARE_JS
                info.challenge_header = headers.get("cf-ray", "")
                info.challenge_cookie = headers.get("set-cookie", "")
            elif "x-px" in headers or "x-p-x" in headers:
                info.challenge_type = ChallengeType.PERIMETERX
            elif "akamai-x-get-client-ip" in headers:
                info.challenge_type = ChallengeType.AKAMAI
            elif any(k in headers for k in ("dd_z", "dd_data", "datadome")):
                info.challenge_type = ChallengeType.DATADOME

        # ── Check response body patterns ────────────────────────────────────────
        if info.challenge_type == ChallengeType.NONE and response_body:
            for challenge_type, patterns in CHALLENGE_PATTERNS.items():
                # URL patterns
                for url_pat in patterns.get("url_patterns", []):
                    if re.search(url_pat, url, re.IGNORECASE):
                        info.challenge_type = challenge_type
                        info.challenge_url = url
                        break

                # Body patterns
                if info.challenge_type == ChallengeType.NONE:
                    for body_pat in patterns.get("body_patterns", []):
                        if re.search(body_pat, body_lower, re.IGNORECASE):
                            info.challenge_type = challenge_type
                            break

                # Header patterns
                if info.challenge_type == ChallengeType.NONE:
                    for hdr, pat in patterns.get("header_patterns", {}).items():
                        if hdr in headers and re.search(pat, str(headers[hdr])):
                            info.challenge_type = challenge_type
                            info.challenge_header = f"{hdr}: {headers[hdr]}"
                            break

                # Cookie patterns
                if info.challenge_type == ChallengeType.NONE and request_cookies:
                    for cookie_pat in patterns.get("cookie_patterns", []):
                        for cookie_val in request_cookies.values():
                            if re.search(cookie_pat, cookie_val):
                                info.challenge_type = challenge_type
                                info.challenge_cookie = cookie_val
                                break

                if info.challenge_type != ChallengeType.NONE:
                    break

        # ── Check redirect chains ───────────────────────────────────────────────
        if status in (302, 303, 307, 308):
            location = headers.get("location", "")
            if location:
                info.redirect_chain.append(location)
                if "challenge" in location.lower() or "captcha" in location.lower():
                    info.challenge_type = ChallengeType.CLOUDFLARE_CHALLENGE
                    info.challenge_url = location

        return info

    def get_domain_key(self, url: str) -> str:
        """Extract the root domain for challenge tracking."""
        parsed = urlparse(url)
        parts = parsed.netloc.split(".")
        if len(parts) >= 2:
            return ".".join(parts[-2:])
        return parsed.netloc

    async def register(self, page) -> None:
        """
        Register route interception handlers on a Playwright page.
        This enables us to catch and respond to anti-bot challenges mid-navigation.
        """
        if self._route_handler_added:
            return

        # ── Intercept ALL requests to detect challenges ──────────────────────────
        async def handle_route(route):
            request = route.request
            url = request.url

            self._total_interceptions += 1

            # Continue with the request
            try:
                response = await route.fetch()
            except Exception as e:
                logger.warning(f"[RouteInt] Fetch failed for {url}: {e}")
                await route.abort()
                return

            status = response.status
            headers = dict(response.headers)
            body = ""

            # Only read body for challenge detection (for text/html responses)
            content_type = headers.get("content-type", "")
            if "text/html" in content_type or "application/json" in content_type:
                try:
                    body = await response.text()
                except Exception:
                    pass

            # Check for challenge
            req_cookies = dict(request.all_headers())
            info = self._detect_challenge(url, headers, status, body, req_cookies)

            if info.challenge_type != ChallengeType.NONE:
                domain_key = self._get_domain_key(url)
                info.challenge_domain = domain_key

                # Update tracking
                if domain_key not in self._challenges:
                    self._challenges[domain_key] = info
                else:
                    existing = self._challenges[domain_key]
                    info.bypass_attempts = existing.bypass_attempts + 1

                logger.warning(
                    f"[RouteInt] Challenge detected: {info.challenge_type.value} "
                    f"on {domain_key} (status={status})"
                )

                # ── Escalate to tier retry if challenge on repeat visit ──────
                if info.bypass_attempts >= 1:
                    # First attempt: try to wait it out
                    logger.info(f"[RouteInt] Challenge persists on {domain_key} — escalating")
                    # Signal to browser_agent that we should switch tiers
                    if self.agent:
                        self.agent._challenge_escalation = True
                        self.agent._challenge_domain = domain_key
                        self.agent._challenge_type = info.challenge_type

                # Call the callback if set
                if self.on_challenge_callback:
                    try:
                        result = await self.on_challenge_callback(info)
                        if result and result.action == "retry":
                            # Retry with modified headers
                            if result.headers_added:
                                override_headers = {**headers, **result.headers_added}
                                await route.fetch(headers=override_headers)
                            await route.continue_()
                            return
                    except Exception as e:
                        logger.warning(f"[RouteInt] Callback error: {e}")

                # Default: just continue (let the page load, AI will see it)
                await route.continue_()
            else:
                # Not a challenge — allow through
                await route.continue_()

        # ── Intercept responses for challenge body analysis ─────────────────────
        async def handle_response(response):
            url = response.url
            status = response.status
            headers = dict(response.headers)

            if status in (403, 429, 503):
                domain_key = self._get_domain_key(url)
                logger.warning(f"[RouteInt] Got {status} from {domain_key} — analyzing...")

                # Try to read the body to confirm challenge
                try:
                    body = await response.text()
                    info = self._detect_challenge(url, headers, status, body)
                    if info.challenge_type != ChallengeType.NONE:
                        self._challenges[domain_key] = info
                        logger.warning(
                            f"[RouteInt] Confirmed {info.challenge_type.value} on {domain_key}"
                        )
                except Exception as e:
                    logger.warning(f"[RouteInt] Could not read 403 body: {e}")

        # Register handlers
        page.on("route", handle_route)
        page.on("response", handle_response)
        self._route_handler_added = True
        logger.info("[RouteInt] Route interception registered")

    def get_domain_challenge(self, url: str) -> Optional[ChallengeInfo]:
        """Return challenge info for a domain if we've recorded one."""
        domain_key = self._get_domain_key(url)
        return self._challenges.get(domain_key)

    def should_escalate(self, url: str) -> bool:
        """Return True if this domain has challenged us before and needs tier escalation."""
        domain_key = self._get_domain_key(url)
        info = self._challenges.get(domain_key)
        return info is not None and info.bypass_attempts >= 1

    def record_bypass_success(self, url: str) -> None:
        """Record that we successfully bypassed a challenge on this domain."""
        domain_key = self._get_domain_key(url)
        if domain_key in self._challenges:
            info = self._challenges[domain_key]
            info.bypass_attempts = 0  # Reset — we succeeded
            logger.info(f"[RouteInt] Bypass confirmed for {domain_key}")

    def get_stats(self) -> Dict[str, Any]:
        """Return interception statistics."""
        return {
            "total_interceptions": self._total_interceptions,
            "challenged_domains": len(self._challenges),
            "challenges": {
                domain: {
                    "type": info.challenge_type.value,
                    "attempts": info.bypass_attempts,
                    "last_seen": time.time() - info.detected_at,
                }
                for domain, info in self._challenges.items()
            },
        }
