"""
antibot_escalation.py — T044: Extreme fallback engine for commercial antibot sites.

This is the CORE of the "every fallback" system. When a site blocks the browser,
this module decides WHAT to do next and DOES it — not just signals.

The escalation chain (8 tiers, most to least aggressive):
  Tier 0: AI CAPTCHA solve (image challenge, no browser restart needed)
  Tier 1: AI CAPTCHA solve + proxy rotate (rotate proxy, solve CAPTCHA, retry)
  Tier 2: Restart browser + rotate proxy + rotate UA/viewport/tz (full reset)
  Tier 3: Switch to Firefox/camoufox (different TLS fingerprint, different renderer)
  Tier 4: Switch to nodriver stealth (most advanced JS spoofing)
  Tier 5: Use session cookie pre-warm (visit Google first, THEN target)
  Tier 6: Use Bright Data unblocker proxy (commercial JS challenge solver at proxy layer)
  Tier 7: Mark as KNOWN LIMITATION + document

Challenge detection:
  1. Route interceptor (header/URL/body patterns) — fast, pre-navigation
  2. AI screenshot analysis — catches JS-layer challenges route interceptor misses
  3. Page title/content scan — "Blocked", "Security Check", "Access Denied"

AI CAPTCHA solving (Tier 0-1):
  Uses MiniMax vision to analyze challenge screenshots.
  - Cloudflare "pick all images" → AI identifies matching images
  - Text challenges → AI reads challenge text, types answer
  - Falls through all tiers → Tier 7 (known limitation)

Usage in browser_agent.py:
    from antibot_escalation import AntibotEscalation
    escalation = AntibotEscalation(self)
    result = await escalation.escalate(reason="challenge_detected", page=page)
    if result["action"] == "restart_tier":
        await self._restart_browser_tier(result["tier"])
"""

import asyncio
import base64
import logging
import random
import time
from enum import Enum
from typing import Optional, Any
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class EscalationTier(Enum):
    """Escalation tiers from least to most aggressive."""
    CAPTCHA_SOLVE = 0      # AI solve image/text CAPTCHA — no browser restart
    CAPTCHA_PROXY = 1      # Rotate proxy + solve CAPTCHA
    RESTART_BROWSER = 2    # Full browser restart + proxy + UA/tz rotate
    SWITCH_FIREFOX = 3     # Switch to Firefox (camoufox) — different TLS/renderer
    SWITCH_NODRIVER = 4    # Switch to nodriver stealth
    SESSION_WARM = 5       # Pre-warm: Google → cookies → target
    UNBLOCKER_PROXY = 6    # Use Bright Data unblocker proxy
    KNOWN_LIMIT = 7        # Give up — document as known limitation


TIER_LABELS = {
    EscalationTier.CAPTCHA_SOLVE: "AI CAPTCHA solve",
    EscalationTier.CAPTCHA_PROXY: "Rotate proxy + AI CAPTCHA solve",
    EscalationTier.RESTART_BROWSER: "Restart browser + rotate proxy/UA",
    EscalationTier.SWITCH_FIREFOX: "Switch to Firefox/camoufox",
    EscalationTier.SWITCH_NODRIVER: "Switch to nodriver stealth",
    EscalationTier.SESSION_WARM: "Session warm-up (Google → target)",
    EscalationTier.UNBLOCKER_PROXY: "Bright Data unblocker proxy",
    EscalationTier.KNOWN_LIMIT: "Known limitation — site needs manual proxy",
}


class ChallengeCategory(Enum):
    """What's actually blocking us."""
    NONE = "none"
    CAPTCHA_IMAGE = "captcha_image"       # Cloudflare "pick all images" / hCaptcha
    CAPTCHA_TEXT = "captcha_text"          # Text input challenge
    CLOUDLARE_JS = "cloudflare_js"        # "Checking your browser" JS challenge
    DATADOME = "datadome"                  # DataDome
    PERIMETERX = "perimeterx"              # PerimeterX
    AKAMAI = "akamai"                      # Akamai
    IP_BLOCK = "ip_block"                   # IP-level 403 (no challenge page)
    UNKNOWN = "unknown"                    # Something else


# ── Challenge page fingerprints ─────────────────────────────────────────────────

CHALLENGE_TITLES = [
    "blocked", "access denied", "forbidden", "security check",
    "checking your browser", "cloudflare", "captcha", "turnstile",
    "please verify you are a human", "ddos guard", "not acceptable",
]

CHALLENGE_BODY_PATTERNS = [
    "cf-challenge", "cloudflare", "ray id", "perimeterx", "px-captcha",
    "datadome", "dd_z", "akamaighost", "access denied",
    "checking your browser", "enable javascript",
    "hcaptcha", "g-recaptcha", "turnstile",
]

CHALLENGE_URL_PATTERNS = [
    "/cdn-cgi/challenge-platform", "/__cf_client_verify",
    "/challenges.cloudflare.com", "/generate_204",
    "captcha", "challenge", "verify", "human", "robot",
]


class AntibotEscalation:
    """
    The "extreme fallback" engine. Analyzes the challenge and decides
    the best escalation path.

    Usage:
        escalation = AntibotEscalation(agent)
        result = await escalation.escalate(reason="challenge_detected", page=page)
        # result = {"action": "restart_tier", "tier": 2, "reason": "...", "next_tier": ...}
    """

    def __init__(self, agent):
        self.agent = agent
        self._tier_history: list[EscalationTier] = []
        self._captcha_solved_count = 0
        self._proxy_rotations = 0
        self._restart_count = 0

    # ── Public API ──────────────────────────────────────────────────────────────

    async def escalate(
        self,
        reason: str,
        page=None,
        screenshot_b64: Optional[str] = None,
        challenge_type: Optional[ChallengeCategory] = None,
    ) -> dict:
        """
        Analyze the current block and decide the next escalation step.

        Returns:
            {
                "action": "continue" | "restart_tier" | "solve_captcha" | "rotate_proxy" | "give_up",
                "tier": EscalationTier value,
                "reason": str,
                "next_tier": EscalationTier (what to try after this if it fails),
                "details": dict (extra info for the agent),
            }
        """
        # Determine what kind of challenge we're facing
        if challenge_type is None:
            challenge_type = await self._detect_challenge_type(page, screenshot_b64)

        logger.info(f"[Escalation] reason={reason} challenge={challenge_type.value} tier_history={self._tier_history}")

        # Pick the best escalation path based on challenge type + what we've tried
        tier = self._pick_tier(challenge_type, reason)
        self._tier_history.append(tier)

        if tier == EscalationTier.CAPTCHA_SOLVE:
            return {
                "action": "solve_captcha",
                "tier": tier,
                "reason": "Image/text CAPTCHA detected — using AI to solve",
                "next_tier": EscalationTier.CAPTCHA_PROXY,
                "details": {"challenge_type": challenge_type.value},
            }

        elif tier == EscalationTier.CAPTCHA_PROXY:
            self._proxy_rotations += 1
            return {
                "action": "rotate_proxy_and_solve_captcha",
                "tier": tier,
                "reason": "Rotating proxy and solving CAPTCHA",
                "next_tier": EscalationTier.RESTART_BROWSER,
                "details": {"challenge_type": challenge_type.value, "rotation": self._proxy_rotations},
            }

        elif tier == EscalationTier.RESTART_BROWSER:
            self._restart_count += 1
            return {
                "action": "restart_browser",
                "tier": tier,
                "reason": "Restarting browser with fresh proxy, UA, viewport, timezone",
                "next_tier": EscalationTier.SWITCH_FIREFOX,
                "details": {"restart_num": self._restart_count, "proxies_rotated": self._proxy_rotations},
            }

        elif tier == EscalationTier.SWITCH_FIREFOX:
            return {
                "action": "switch_engine",
                "tier": tier,
                "reason": "Switching to Firefox/camoufox — different TLS fingerprint + renderer",
                "next_tier": EscalationTier.SWITCH_NODRIVER,
                "details": {"engine": "camoufox"},
            }

        elif tier == EscalationTier.SWITCH_NODRIVER:
            return {
                "action": "switch_engine",
                "tier": tier,
                "reason": "Switching to nodriver stealth browser — most advanced JS spoofing",
                "next_tier": EscalationTier.SESSION_WARM,
                "details": {"engine": "nodriver"},
            }

        elif tier == EscalationTier.SESSION_WARM:
            return {
                "action": "session_warm_up",
                "tier": tier,
                "reason": "Pre-warming session: visit Google first, establish cookies, then target",
                "next_tier": EscalationTier.UNBLOCKER_PROXY,
                "details": {},
            }

        elif tier == EscalationTier.UNBLOCKER_PROXY:
            return {
                "action": "unblocker_proxy",
                "tier": tier,
                "reason": "Bright Data unblocker proxy — solves JS challenge at proxy layer",
                "next_tier": EscalationTier.KNOWN_LIMIT,
                "details": {"note": "Requires BRIGHTDATA_ZONE with unblocker type"},
            }

        else:  # KNOWN_LIMIT
            return {
                "action": "give_up",
                "tier": tier,
                "reason": self._build_known_limit_note(challenge_type, reason),
                "next_tier": None,
                "details": {
                    "challenge_type": challenge_type.value,
                    "tiers_tried": [t.value for t in self._tier_history],
                    "recommendation": self._get_recommendation(challenge_type),
                },
            }

    async def solve_captcha(self, page, challenge_type: ChallengeCategory) -> dict:
        """
        Use AI vision to solve image CAPTCHAs (Cloudflare "pick all images", hCaptcha).
        Uses MiniMax vision via mcp_MiniMax_understand_image.

        For text challenges: reads the challenge text and types the answer.
        """
        from ai_router import call_minimax

        self._captcha_solved_count += 1

        if challenge_type == ChallengeCategory.CAPTCHA_IMAGE:
            return await self._solve_image_captcha(page)
        elif challenge_type == ChallengeCategory.CAPTCHA_TEXT:
            return await self._solve_text_captcha(page)
        else:
            return {"success": False, "reason": "Not an image/text CAPTCHA"}

    # ── Private: tier selection ───────────────────────────────────────────────

    def _pick_tier(
        self,
        challenge_type: ChallengeCategory,
        reason: str,
    ) -> EscalationTier:
        """
        Pick the best escalation tier based on challenge + history.
        """
        # If we've already tried everything, give up
        if self._tier_history:
            last = self._tier_history[-1]
            if last == EscalationTier.KNOWN_LIMIT:
                return EscalationTier.KNOWN_LIMIT

        # CAPTCHAs get immediate AI solve attempt (Tier 0)
        if challenge_type in (ChallengeCategory.CAPTCHA_IMAGE, ChallengeCategory.CAPTCHA_TEXT):
            if self._captcha_solved_count < 2:
                return EscalationTier.CAPTCHA_SOLVE
            else:
                return EscalationTier.CAPTCHA_PROXY

        # JS challenge without CAPTCHA → rotate proxy + restart browser
        if challenge_type == ChallengeCategory.CLOUDLARE_JS:
            if self._restart_count < 1:
                return EscalationTier.RESTART_BROWSER
            elif self._restart_count < 2:
                return EscalationTier.SWITCH_FIREFOX
            else:
                return EscalationTier.UNBLOCKER_PROXY

        # DataDome / PerimeterX → these need residential proxy
        if challenge_type in (ChallengeCategory.DATADOME, ChallengeCategory.PERIMETERX):
            if self._restart_count < 1:
                return EscalationTier.SESSION_WARM
            else:
                return EscalationTier.UNBLOCKER_PROXY

        # IP block → just rotate proxy
        if challenge_type == ChallengeCategory.IP_BLOCK:
            if self._proxy_rotations < 3:
                return EscalationTier.CAPTCHA_PROXY
            else:
                return EscalationTier.UNBLOCKER_PROXY

        # Unknown block → aggressive escalation
        if self._restart_count == 0:
            return EscalationTier.RESTART_BROWSER
        elif self._restart_count == 1:
            return EscalationTier.SWITCH_FIREFOX
        elif self._restart_count == 2:
            return EscalationTier.SWITCH_NODRIVER
        else:
            return EscalationTier.KNOWN_LIMIT

    # ── Private: challenge detection ─────────────────────────────────────────

    async def _detect_challenge_type(
        self,
        page,
        screenshot_b64: Optional[str] = None,
    ) -> ChallengeCategory:
        """
        Detect what kind of block we're facing.
        Uses route interceptor data + page title/body + AI screenshot analysis.
        """
        # 1. Check route interceptor (already has challenge type from headers)
        if self.agent._route_interceptor and self.agent.page:
            domain_key = self.agent._route_interceptor.get_domain_key(self.agent.page.url)
            info = self.agent._route_interceptor.get_domain_challenge(self.agent.page.url)
            if info:
                return self._route_info_to_category(info.challenge_type.value if hasattr(info.challenge_type, 'value') else str(info.challenge_type))

        # 2. Page title/body scan (fast)
        if page:
            try:
                title = (await page.title()).lower()
                url = (page.url or "").lower()

                for kw in CHALLENGE_TITLES:
                    if kw in title:
                        # Narrow down
                        if "captcha" in title or "turnstile" in title or "hcaptcha" in title:
                            return ChallengeCategory.CAPTCHA_IMAGE
                        if "cloudflare" in title or "checking your browser" in title:
                            return ChallengeCategory.CLOUDLARE_JS
                        if "access denied" in title or "forbidden" in title:
                            return ChallengeCategory.IP_BLOCK

                for pat in CHALLENGE_URL_PATTERNS:
                    if pat in url:
                        if "captcha" in url or "turnstile" in url:
                            return ChallengeCategory.CAPTCHA_IMAGE
                        if "challenge" in url or "cf挑战" in url:
                            return ChallengeCategory.CLOUDLARE_JS

                body_text = ""
                try:
                    body_text = await page.inner_text("body")
                    body_text = body_text.lower()
                except Exception:
                    pass

                for pat in CHALLENGE_BODY_PATTERNS:
                    if pat in body_text:
                        if "perimeterx" in body_text or "px-captcha" in body_text:
                            return ChallengeCategory.PERIMETERX
                        if "datadome" in body_text or "dd_z" in body_text:
                            return ChallengeCategory.DATADOME
                        if "cf-challenge" in body_text or "cloudflare" in body_text:
                            return ChallengeCategory.CLOUDLARE_JS
                        if "captcha" in body_text or "hcaptcha" in body_text:
                            return ChallengeCategory.CAPTCHA_IMAGE
            except Exception as e:
                logger.warning(f"[Escalation] Page scan error: {e}")

        # 3. AI screenshot analysis (most reliable for JS-layer challenges)
        if screenshot_b64:
            ai_category = await self._ai_analyze_screenshot(screenshot_b64)
            if ai_category != ChallengeCategory.NONE:
                return ai_category

        return ChallengeCategory.UNKNOWN

    async def _ai_analyze_screenshot(self, screenshot_b64: str) -> ChallengeCategory:
        """
        Use MiniMax vision to look at the screenshot and decide if it's a challenge.
        This catches JS-layer challenges that route interception misses.
        """
        try:
            from ai_router import call_minimax

            # Save screenshot to temp file for vision analysis
            import tempfile, os
            with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False, mode="wb") as f:
                img_data = base64.b64decode(screenshot_b64)
                f.write(img_data)
                tmp_path = f.name

            try:
                # Use MiniMax vision to analyze
                prompt = (
                    "Look at this screenshot of a web page. Is this page showing:\n"
                    "1. A CAPTCHA challenge (Cloudflare 'pick all images', hCaptcha, reCAPTCHA, or Turnstile)\n"
                    "2. A Cloudflare 'Checking your browser' JavaScript challenge page\n"
                    "3. An 'Access Denied' / '403 Forbidden' page\n"
                    "4. A normal website page (job listings, search results, product page, etc.)\n"
                    "5. A PerimeterX or DataDome bot detection page\n\n"
                    "Describe what you see briefly, then answer: CAPTCHA / CLOUDFLARE_JS / ACCESS_DENIED / NORMAL / DATADOME_PERIMETERX / UNKNOWN"
                )

                messages = [
                    {"role": "user", "content": [
                        {"type": "image_url", "image_url": {"url": f"file://{tmp_path}"}},
                        {"type": "text", "text": prompt},
                    ]}
                ]

                answer, _, _ = await call_minimax(
                    messages,
                    model_name="MiniMax-M2.7",
                    max_tokens=256,
                )

                answer_upper = answer.upper()
                if "CAPTCHA" in answer_upper or "HCAPTCHA" in answer_upper or "TURNSTILE" in answer_upper:
                    return ChallengeCategory.CAPTCHA_IMAGE
                if "CLOUDFLARE_JS" in answer_upper or "CHECKING YOUR BROWSER" in answer_upper:
                    return ChallengeCategory.CLOUDLARE_JS
                if "ACCESS DENIED" in answer_upper or "FORBIDDEN" in answer_upper:
                    return ChallengeCategory.IP_BLOCK
                if "DATADOME" in answer_upper or "PERIMETERX" in answer_upper:
                    return ChallengeCategory.DATADOME
                if "NORMAL" in answer_upper:
                    return ChallengeCategory.NONE
                return ChallengeCategory.UNKNOWN

            finally:
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass

        except Exception as e:
            logger.warning(f"[Escalation] AI screenshot analysis failed: {e}")
            return ChallengeCategory.UNKNOWN

    async def _solve_image_captcha(self, page) -> dict:
        """
        Solve Cloudflare "pick all images" or hCaptcha using AI vision.
        1. Find all image options on the page
        2. Screenshot each one + the challenge description
        3. Send to MiniMax vision to identify correct images
        4. Click the correct ones
        """
        try:
            from ai_router import call_minimax

            # Find the challenge description text
            description = ""
            try:
                # Cloudflare-style challenge description
                desc_el = await page.query_selector(".cf-challenge-center, #cf-challenge-center, [class*='challenge'], .challenge-text")
                if desc_el:
                    description = await desc_el.inner_text()
            except Exception:
                pass

            if not description:
                try:
                    body = await page.inner_text("body")
                    # Find text around the image grid
                    lines = [l.strip() for l in body.split("\n") if l.strip()]
                    description = " ".join(lines[:5])
                except Exception:
                    description = "Select all images that match the description"

            # Find all clickable image options
            image_options = []
            try:
                # Try multiple selectors for different CAPTCHA types
                selectors = [
                    ".task-image img",
                    ".captcha-img",
                    "[data-type='image'] img",
                    ".cf-img-radio img",
                    "img[src*='challenge']",
                    ".hcaptcha .chunk img",
                ]
                for sel in selectors:
                    els = await page.query_selector_all(sel)
                    for el in els:
                        src = await el.get_attribute("src")
                        if src and src not in [o["src"] for o in image_options]:
                            image_options.append({"selector": sel, "src": src, "el": el})
            except Exception as e:
                logger.warning(f"[Escalation] Finding image options: {e}")

            if not image_options:
                return {"success": False, "reason": "No image options found on CAPTCHA page"}

            # Screenshot the description area
            challenge_desc_screenshot = None
            try:
                desc_el = await page.query_selector(".cf-challenge-center, #challenge-form, body")
                if desc_el:
                    challenge_desc_screenshot = await desc_el.screenshot()
            except Exception:
                pass

            # Send all images to AI vision for analysis
            # For each image, we need to decide if it matches the challenge
            selected_indices = []

            for i, opt in enumerate(image_options[:9]):  # cap at 9 images
                try:
                    img_b64 = await opt["el"].screenshot()
                    if not img_b64:
                        continue

                    import tempfile, os
                    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False, mode="wb") as f:
                        f.write(base64.b64decode(img_b64))
                        tmp_path = f.name

                    try:
                        prompt = (
                            f"Challenge description: {description}\n\n"
                            f"Look at this image (image #{i+1} of the CAPTCHA options).\n"
                            f"Does this image match what the challenge is asking for?\n"
                            f"Answer YES or NO only."
                        )

                        messages = [
                            {"role": "user", "content": [
                                {"type": "image_url", "image_url": {"url": f"file://{tmp_path}"}},
                                {"type": "text", "text": prompt},
                            ]}
                        ]

                        answer, _, _ = await call_minimax(
                            messages,
                            model_name="MiniMax-M2.7",
                            max_tokens=32,
                        )

                        if "YES" in answer.upper():
                            selected_indices.append(i)

                    finally:
                        try:
                            os.unlink(tmp_path)
                        except Exception:
                            pass

                except Exception as e:
                    logger.warning(f"[Escalation] Image {i} analysis failed: {e}")

            # Click selected images
            clicked = 0
            for idx in selected_indices:
                try:
                    await image_options[idx]["el"].click()
                    clicked += 1
                    await asyncio.sleep(0.5)
                except Exception as e:
                    logger.warning(f"[Escalation] Clicking image {idx}: {e}")

            if clicked > 0:
                # Look for submit/verify button
                try:
                    submit_selectors = ["#challenge-submit", ".submit-button", "button[type='submit']"]
                    for sel in submit_selectors:
                        btn = await page.query_selector(sel)
                        if btn:
                            await btn.click()
                            await asyncio.sleep(2)
                            break
                except Exception:
                    pass

                return {"success": True, "images_clicked": clicked}

            return {"success": False, "reason": "No images selected"}

        except Exception as e:
            logger.error(f"[Escalation] CAPTCHA solve error: {e}")
            return {"success": False, "reason": str(e)}

    async def _solve_text_captcha(self, page) -> dict:
        """
        Solve text/input CAPTCHAs (Cloudflare text challenge, email regex, etc.)
        Reads the challenge text, sends to AI, types the answer.
        """
        try:
            from ai_router import call_minimax

            # Find the text input field
            input_field = None
            try:
                input_field = await page.query_selector("input[type='text'], input[name*='challenge'], input[id*='challenge'], input[placeholder*=' ']")
            except Exception:
                pass

            if not input_field:
                return {"success": False, "reason": "No text input found on CAPTCHA page"}

            # Find challenge text
            challenge_text = ""
            try:
                # Try to find description
                desc_els = await page.query_selector_all("p, label, .challenge-text")
                for el in desc_els[:3]:
                    t = await el.inner_text()
                    if t and len(t) > 10:
                        challenge_text += " " + t
                challenge_text = challenge_text.strip()
            except Exception:
                pass

            if not challenge_text:
                challenge_text = "Please complete this security check"

            # Use AI to generate answer
            prompt = (
                f"Security challenge text: '{challenge_text}'\n\n"
                f"What is the correct answer to type? "
                f"(If it's an email regex, give an example email. "
                f"If it's a math problem, give the answer. "
                f"If it's a text challenge, give the expected text.) "
                f"Answer with ONLY the answer text, nothing else."
            )

            messages = [{"role": "user", "content": prompt}]
            answer, _, _ = await call_minimax(
                messages,
                model_name="MiniMax-M2.7",
                max_tokens=64,
            )
            answer = answer.strip()

            if answer:
                await input_field.fill(answer)
                await asyncio.sleep(0.5)

                # Try to submit
                try:
                    submit = await page.query_selector("button[type='submit'], #challenge-submit, .verify-button")
                    if submit:
                        await submit.click()
                        await asyncio.sleep(2)
                except Exception:
                    pass

                return {"success": True, "answer": answer[:50]}

            return {"success": False, "reason": "AI did not return an answer"}

        except Exception as e:
            logger.error(f"[Escalation] Text CAPTCHA solve error: {e}")
            return {"success": False, "reason": str(e)}

    # ── Private: helpers ───────────────────────────────────────────────────────

    def _route_info_to_category(self, route_type: str) -> ChallengeCategory:
        route_type_lower = route_type.lower()
        if "cloudflare" in route_type_lower or "cf_" in route_type_lower:
            return ChallengeCategory.CLOUDLARE_JS
        if "captcha" in route_type_lower or "hcaptcha" in route_type_lower or "recaptcha" in route_type_lower:
            return ChallengeCategory.CAPTCHA_IMAGE
        if "datadome" in route_type_lower or "datadome" in route_type_lower:
            return ChallengeCategory.DATADOME
        if "perimeterx" in route_type_lower or "px3" in route_type_lower:
            return ChallengeCategory.PERIMETERX
        if "akamai" in route_type_lower:
            return ChallengeCategory.AKAMAI
        return ChallengeCategory.UNKNOWN

    def _build_known_limit_note(self, challenge_type: ChallengeCategory, reason: str) -> str:
        notes = {
            ChallengeCategory.DATADOME: (
                "DataDome detected — blocks based on mouse/keyboard behavior patterns and browser fingerprinting. "
                "Free/datacenter proxies and standard browsers cannot bypass it. "
                "Solution: Bright Data unblocker zone with residential IPs."
            ),
            ChallengeCategory.PERIMETERX: (
                "PerimeterX detected — blocks based on browser fingerprinting and behavior analysis. "
                "Solution: Bright Data unblocker proxy or Oxylabs residential proxy."
            ),
            ChallengeCategory.CLOUDLARE_JS: (
                "Cloudflare JS challenge persisted through all fallback tiers. "
                "This site needs residential proxy or unblocker proxy to solve the JS challenge at the network layer."
            ),
            ChallengeCategory.IP_BLOCK: (
                "IP-level 403 block — the site's WAF has blocked this IP. "
                "Rotating residential proxies (Bright Data/Oxylabs) required."
            ),
            ChallengeCategory.CAPTCHA_IMAGE: (
                "Image CAPTCHA could not be solved automatically. "
                "Manual intervention required or 2Captcha/Anti-Captcha API needed."
            ),
            ChallengeCategory.UNKNOWN: (
                f"Unknown blocking mechanism: {reason}. "
                "This site uses an antibot system not yet supported. "
                "Document the site + blocking pattern and add to site_overrides.py."
            ),
        }
        return notes.get(challenge_type, f"Unknown block: {reason}")

    def _get_recommendation(self, challenge_type: ChallengeCategory) -> str:
        recs = {
            ChallengeCategory.DATADOME: "PROXY_PROVIDER=brightdata-unblock + BRIGHTDATA_ZONE=unblocker-residential",
            ChallengeCategory.PERIMETERX: "PROXY_PROVIDER=brightdata-unblock",
            ChallengeCategory.CLOUDLARE_JS: "PROXY_PROVIDER=brightdata-unblock",
            ChallengeCategory.IP_BLOCK: "PROXY_PROVIDER=oxylabs or brightdata",
            ChallengeCategory.CAPTCHA_IMAGE: "Use 2Captcha.com or Anti-Captcha.com API",
            ChallengeCategory.UNKNOWN: "Document blocking pattern and add to site_overrides.py",
        }
        return recs.get(challenge_type, "No automatic solution available")
