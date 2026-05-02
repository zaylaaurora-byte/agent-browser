"""
nodriver_bridge.py — T036: Connect nodriver stealth browser to Playwright via CDP

nodriver (by ultrafunkamsterdam) launches Chrome with stealth patches that remove
~15 automation detection signals that standard Playwright/Chrome don't cover.

This bridge lets Playwright use nodriver's browser via connect_over_cdp(ws_url),
giving us: Playwright API + nodriver stealth + our existing TLS/JS spoofing.

Usage:
    from nodriver_bridge import NodriverBridge
    bridge = NodriverBridge()
    pw, browser, page = await bridge.start()
    # Use Playwright API normally — all actions go through nodriver's stealth browser
    await page.goto('https://example.com')
    await bridge.stop()

Environment variables:
    NODRIVER_HEADLESS   : 0=visible, 1=headless (default: 1)
    NODRIVER_PROXY     : proxy URL, e.g. http://user:pass@host:port
    NODRIVER_USER_DATA_DIR : path to persistent Chrome profile (optional)
"""

from __future__ import annotations

import asyncio
import os
import sys
import logging
from typing import Optional, Tuple, Any

logger = logging.getLogger(__name__)

# Lazy import — only load when actually needed (takes ~100ms)
_nodriver = None
_playwright = None


def _get_nodriver():
    global _nodriver
    if _nodriver is None:
        import nodriver as _nd
        _nodriver = _nd
    return _nodriver


async def _get_playwright():
    global _playwright
    if _playwright is None:
        pw_module = await import_playwright()
        _playwright = pw_module
    return _playwright


async def import_playwright():
    from playwright.async_api import async_playwright
    return await async_playwright().__aenter__()


class NodriverBridge:
    """
    Manages nodriver + Playwright CDP bridge lifecycle.

    Pattern:
        bridge = NodriverBridge()
        pw, pw_browser, page = await bridge.start()
        # page is a standard Playwright Page — use .goto(), .click(), etc.
        await bridge.stop()
    """

    def __init__(
        self,
        headless: bool = True,
        proxy: Optional[str] = None,
        user_data_dir: Optional[str] = None,
        extra_args: Optional[list] = None,
    ):
        self.headless = headless
        self.proxy = proxy or os.getenv("NODRIVER_PROXY") or None
        self.user_data_dir = user_data_dir
        self.extra_args = extra_args or []

        self._nodriver_browser = None   # raw nodriver Browser
        self._pw: Optional[Any] = None   # Playwright instance
        self._pw_browser: Optional[Any] = None  # Playwright Browser (connected via CDP)

    # ── Public API ────────────────────────────────────────────────────────────

    async def start(self) -> Tuple[Any, Any, Any]:
        """
        Launch nodriver browser and connect Playwright over CDP.

        Returns:
            (playwright, playwright_browser, playwright_page)

        playwright_browser is a Playwright Browser object connected to nodriver's
        stealth browser — use it to create contexts, new pages, etc.

        playwright_page is the first/new page ready to use.

        Example:
            pw, browser, page = await bridge.start()
            await page.goto('https://example.com')
            await browser.close()
            await pw.__aexit__(None, None, None)
        """
        logger.info("[nodriver] Starting nodriver browser...")
        nd = _get_nodriver()

        # Build nodriver start kwargs
        nd_kwargs = {"headless": self.headless}
        if self.proxy:
            nd_kwargs["proxy"] = self.proxy
        if self.user_data_dir:
            nd_kwargs["user_data_dir"] = self.user_data_dir

        try:
            self._nodriver_browser = await nd.start(**nd_kwargs)
        except Exception as e:
            logger.error(f"[nodriver] Failed to start: {e}")
            raise

        ws_url = self._nodriver_browser.websocket_url
        logger.info(f"[nodriver] Browser started. CDP ws:// {ws_url}")

        # Connect Playwright to nodriver's CDP websocket
        self._pw = await import_playwright()
        try:
            self._pw_browser = await self._pw.chromium.connect_over_cdp(ws_url)
        except Exception as e:
            logger.error(f"[nodriver] Playwright CDP connect failed: {e}")
            await self._stop_nodriver()
            raise

        logger.info("[nodriver] Playwright connected to nodriver via CDP")

        # Create a fresh page
        page = await self._pw_browser.new_page()

        return self._pw, self._pw_browser, page

    async def stop(self):
        """Clean shutdown of Playwright + nodriver browser."""
        logger.info("[nodriver] Stopping...")
        if self._pw_browser:
            try:
                await self._pw_browser.close()
            except Exception as e:
                logger.warning(f"[nodriver] pw_browser.close: {e}")
        if self._pw:
            try:
                # Playwright has stop(), not __aexit__
                await self._pw.stop()
            except Exception as e:
                logger.warning(f"[nodriver] pw.stop: {e}")
        await self._stop_nodriver()
        logger.info("[nodriver] Stopped")

    async def _stop_nodriver(self):
        """Stop nodriver browser (not async)."""
        if self._nodriver_browser:
            try:
                self._nodriver_browser.stop()
            except Exception as e:
                logger.warning(f"[nodriver] browser.stop: {e}")

    # ── Context manager ───────────────────────────────────────────────────────

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.stop()


# ── Standalone test ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    async def main():
        url = sys.argv[1] if len(sys.argv) > 1 else "https://httpbin.org/html"
        async with NodriverBridge() as bridge:
            pw, browser, page = await bridge.start()
            resp = await page.goto(url, wait_until="domcontentloaded", timeout=20000)
            print(f"Status: {resp.status}")
            print(f"Title:  {await page.title()}")
            print(f"URL:    {page.url}")

    asyncio.run(main())
