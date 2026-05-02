"""
CAPTCHA Solver — T010
Routes CAPTCHA solving to 2Captcha, Anti-Captcha, or CapSolver.
"""

import asyncio
import logging
import time
import httpx
from typing import Optional

logger = logging.getLogger(__name__)

# ─── CAPTCHA type constants ───────────────────────────────────────────────────
TYPE_HCAPTCHA = "hcaptcha"
TYPE_RECAPTCHA_V2 = "recaptcha-v2"
TYPE_RECAPTCHA_V3 = "recaptcha-v3"
TYPE_TURNSTILE = "turnstile"
TYPE_CLOUDflare = "cloudflare"


# ─── 2Captcha ─────────────────────────────────────────────────────────────────
async def solve_2captcha(
    api_key: str,
    captcha_type: str,
    site_key: str,
    url: str,
    **kwargs,
) -> Optional[str]:
    """
    Solve CAPTCHA via 2Captcha (https://2captcha.com).
    Returns the solved token string, or None on failure.

    captcha_type: hcaptcha | recaptcha-v2 | recaptcha-v3 | turnstile
    """
    if not api_key:
        logger.warning("[2Captcha] No API key provided")
        return None

    pageurl = url
    # Map our types to 2Captcha's API params
    if captcha_type == TYPE_RECAPTCHA_V3:
        soft_id = kwargs.get("soft_id", "")
        action = kwargs.get("action", "verify")
        min_score = kwargs.get("min_score", 0.3)
        req_payload = {
            "googlekey": site_key,
            "pageurl": pageurl,
            "method": "userrecaptcha",
            "version": "v3",
            "action": action,
            "min_score": min_score,
            "key": api_key,
            "soft_id": soft_id,
            "json": 1,
        }
    elif captcha_type == TYPE_RECAPTCHA_V2:
        req_payload = {
            "googlekey": site_key,
            "pageurl": pageurl,
            "method": "userrecaptcha",
            "key": api_key,
            "json": 1,
        }
    elif captcha_type == TYPE_HCAPTCHA:
        req_payload = {
            "sitekey": site_key,
            "pageurl": pageurl,
            "method": "hcaptcha",
            "key": api_key,
            "json": 1,
        }
    elif captcha_type == TYPE_TURNSTILE:
        req_payload = {
            "sitekey": site_key,
            "pageurl": pageurl,
            "method": "turnstile",
            "key": api_key,
            "json": 1,
        }
    else:
        logger.warning(f"[2Captcha] Unknown CAPTCHA type: {captcha_type}")
        return None

    captcha_id = None
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            # Submit
            submit_resp = await client.get("https://2captcha.com/in.php", params=req_payload)
            submit_data = submit_resp.text.strip()

            if submit_data.startswith("OK|"):
                captcha_id = submit_data.split("|")[1]
                logger.info(f"[2Captcha] Submitted, ID: {captcha_id}")
            elif submit_data == "ERROR_WRONG_USER_KEY":
                logger.error("[2Captcha] ERROR_WRONG_USER_KEY")
                return None
            elif submit_data == "ERROR_ZERO_BALANCE":
                logger.error("[2Captcha] ERROR_ZERO_BALANCE")
                return None
            else:
                logger.error(f"[2Captcha] Submit error: {submit_data}")
                return None

            # Poll for result (max 120s)
            for _ in range(120):
                await asyncio.sleep(5)
                poll_resp = await client.get(
                    "https://2captcha.com/res.php",
                    params={"key": api_key, "action": "get", "id": captcha_id, "json": 1},
                )
                poll_data = poll_resp.text.strip()

                if poll_data == "CAPCHA_NOT_READY":
                    continue

                if poll_data.startswith("OK|"):
                    token = poll_data.split("|", 1)[1]
                    logger.info("[2Captcha] Solved successfully")
                    return token

                logger.error(f"[2Captcha] Poll error: {poll_data}")
                return None

            logger.warning("[2Captcha] Timeout waiting for solve")
            return None

    except Exception as e:
        logger.error(f"[2Captcha] Exception: {e}")
        return None


# ─── Anti-Captcha (anti-captcha.com) ─────────────────────────────────────────
async def solve_anticaptcha(
    api_key: str,
    captcha_type: str,
    site_key: str,
    url: str,
    **kwargs,
) -> Optional[str]:
    """
    Solve CAPTCHA via Anti-Captcha (https://anti-captcha.com).
    Returns the solved token string, or None on failure.
    """
    if not api_key:
        logger.warning("[Anti-Captcha] No API key provided")
        return None

    pageurl = url

    if captcha_type == TYPE_HCAPTCHA:
        task_payload = {
            "type": "HCaptchaTaskProxyless",
            "websiteURL": pageurl,
            "websiteKey": site_key,
        }
    elif captcha_type == TYPE_RECAPTCHA_V2:
        task_payload = {
            "type": "RecaptchaV2TaskProxyless",
            "websiteURL": pageurl,
            "websiteKey": site_key,
        }
    elif captcha_type == TYPE_RECAPTCHA_V3:
        task_payload = {
            "type": "RecaptchaV3TaskProxyless",
            "websiteURL": pageurl,
            "websiteKey": site_key,
            "minScore": kwargs.get("min_score", 0.3),
            "action": kwargs.get("action", "verify"),
        }
    elif captcha_type == TYPE_TURNSTILE:
        task_payload = {
            "type": "TurnstileTaskProxyless",
            "websiteURL": pageurl,
            "websiteKey": site_key,
        }
    else:
        logger.warning(f"[Anti-Captcha] Unknown CAPTCHA type: {captcha_type}")
        return None

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            # Create task
            create_resp = await client.post(
                "https://api.anti-captcha.com/createTask",
                json={"clientKey": api_key, "task": task_payload},
            )
            create_data = create_resp.json()
            if create_data.get("errorId") != 0:
                logger.error(f"[Anti-Captcha] Create error: {create_data.get('errorDescription')}")
                return None

            task_id = create_data["taskId"]
            logger.info(f"[Anti-Captcha] Task created, ID: {task_id}")

            # Poll for result
            for _ in range(120):
                await asyncio.sleep(5)
                poll_resp = await client.post(
                    "https://api.anti-captcha.com/getTaskResult",
                    json={"clientKey": api_key, "taskId": task_id},
                )
                poll_data = poll_resp.json()

                if poll_data.get("status") == "processing":
                    continue

                if poll_data.get("status") == "ready":
                    solution = poll_data.get("solution", {})
                    token = solution.get("gRecaptchaResponse") or solution.get("token") or solution.get("g-captcha-response")
                    logger.info("[Anti-Captcha] Solved successfully")
                    return token

                logger.error(f"[Anti-Captcha] Unexpected result: {poll_data}")
                return None

            logger.warning("[Anti-Captcha] Timeout waiting for solve")
            return None

    except Exception as e:
        logger.error(f"[Anti-Captcha] Exception: {e}")
        return None


# ─── CapSolver (capsolver.com) ─────────────────────────────────────────────────
async def solve_capsolver(
    api_key: str,
    site_key: str,
    url: str,
    captcha_type: str,
    **kwargs,
) -> Optional[str]:
    """
    Solve CAPTCHA via CapSolver (https://capsolver.com).
    Returns the solved token string, or None on failure.
    """
    if not api_key:
        logger.warning("[CapSolver] No API key provided")
        return None

    pageurl = url

    if captcha_type == TYPE_HCAPTCHA:
        task_type = "HCaptchaTask"
    elif captcha_type == TYPE_RECAPTCHA_V2:
        task_type = "ReCaptchaV2Task"
    elif captcha_type == TYPE_RECAPTCHA_V3:
        task_type = "ReCaptchaV3Task"
        kwargs.setdefault("minScore", 0.3)
    elif captcha_type == TYPE_TURNSTILE:
        task_type = "TurnstileTask"
    else:
        logger.warning(f"[CapSolver] Unknown CAPTCHA type: {captcha_type}")
        return None

    task_payload = {
        "type": task_type,
        "websiteURL": pageurl,
        "websiteKey": site_key,
        **kwargs,
    }

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            # Create task
            create_resp = await client.post(
                "https://api.capsolver.com/createTask",
                json={"clientKey": api_key, "task": task_payload},
            )
            create_data = create_resp.json()
            if create_data.get("errorId") != 0:
                logger.error(f"[CapSolver] Create error: {create_data}")
                return None

            task_id = create_data["taskId"]
            logger.info(f"[CapSolver] Task created, ID: {task_id}")

            # Poll for result
            for _ in range(120):
                await asyncio.sleep(5)
                poll_resp = await client.post(
                    "https://api.capsolver.com/getTaskResult",
                    json={"clientKey": api_key, "taskId": task_id},
                )
                poll_data = poll_resp.json()

                if poll_data.get("status") == "processing":
                    continue

                if poll_data.get("status") == "ready":
                    token = poll_data.get("solution", {}).get("gRecaptchaResponse")
                    logger.info("[CapSolver] Solved successfully")
                    return token

                logger.error(f"[CapSolver] Unexpected result: {poll_data}")
                return None

            logger.warning("[CapSolver] Timeout waiting for solve")
            return None

    except Exception as e:
        logger.error(f"[CapSolver] Exception: {e}")
        return None


# ─── Router ────────────────────────────────────────────────────────────────────
async def solve_captcha(
    api_key: str,
    captcha_type: str,
    site_key: str,
    url: str,
    provider: str = "2captcha",
    **kwargs,
) -> Optional[str]:
    """
    Route CAPTCHA solving to the configured provider.
    provider: "2captcha" | "anticaptcha" | "capsolver"
    """
    logger.info(f"[CAPTCHA Solver] provider={provider} type={captcha_type} site={url}")

    if provider == "anticaptcha":
        return await solve_anticaptcha(api_key, captcha_type, site_key, url, **kwargs)
    elif provider == "capsolver":
        return await solve_capsolver(api_key, site_key, url, captcha_type, **kwargs)
    else:
        # Default to 2Captcha
        return await solve_2captcha(api_key, captcha_type, site_key, url, **kwargs)


# ─── Detection helpers ─────────────────────────────────────────────────────────
def detect_site_key(page, captcha_type: str) -> Optional[str]:
    """
    Extract the sitekey from the page for the given CAPTCHA type.
    Returns the sitekey string or None if not found.
    """
    try:
        if captcha_type == TYPE_HCAPTCHA:
            # hCaptcha: data-sitekey attribute on .h-captcha iframe or div
            selector = '[data-sitekey]'
            el = page.query_selector(selector)
            if el:
                return el.get_attribute("data-sitekey")
            # Fallback: look in page source
            return None

        elif captcha_type in (TYPE_RECAPTCHA_V2, TYPE_RECAPTCHA_V3):
            # reCAPTCHA: data-sitekey on .g-recaptcha or the div containing it
            selector = '[data-sitekey]'
            el = page.query_selector(selector)
            if el:
                return el.get_attribute("data-sitekey")
            return None

        elif captcha_type == TYPE_TURNSTILE:
            # Cloudflare Turnstile: data-sitekey on .cf-turnstile or the challenge div
            selector = '[data-sitekey]'
            el = page.query_selector(selector)
            if el:
                return el.get_attribute("data-sitekey")
            return None

    except Exception as e:
        logger.warning(f"[CAPTCHA Detection] Error extracting sitekey: {e}")

    return None


def detect_and_solve_captcha(
    page,
    api_key: str,
    provider: str = "2captcha",
) -> Optional[str]:
    """
    Detect CAPTCHA type on the page and attempt to solve it.
    Returns the solved token, or None if no CAPTCHA found / solve failed.

    Call this when CAPTCHA is detected during page analysis.
    """
    # Determine CAPTCHA type from page
    captcha_type = None
    try:
        # Try Cloudflare Turnstile first
        if page.query_selector('.cf-turnstile, [class*="turnstile"], [id*="turnstile"]'):
            captcha_type = TYPE_TURNSTILE

        # Try hCaptcha
        if page.query_selector('.h-captcha, [class*="hcaptcha"]'):
            captcha_type = TYPE_HCAPTCHA

        # Try reCAPTCHA
        if page.query_selector('.g-recaptcha, [class*="recaptcha"]'):
            captcha_type = TYPE_RECAPTCHA_V2

    except Exception as e:
        logger.warning(f"[CAPTCHA Detection] Error: {e}")
        return None

    if not captcha_type:
        logger.info("[CAPTCHA Detection] No CAPTCHA found on page")
        return None

    site_key = detect_site_key(page, captcha_type)
    if not site_key:
        logger.warning(f"[CAPTCHA Detection] Could not extract sitekey for {captcha_type}")
        return None

    url = page.url
    return asyncio.get_event_loop().run_until_complete(
        solve_captcha(api_key, captcha_type, site_key, url, provider)
    )
