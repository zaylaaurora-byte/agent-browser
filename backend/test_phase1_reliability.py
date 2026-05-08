import asyncio
import os

from browser_agent import BrowserAgent


class _DummyPage:
    def __init__(self, url: str):
        self.url = url

    async def title(self):
        return "Dummy Title"

    async def goto(self, url, wait_until="domcontentloaded", timeout=20000):
        self.url = url
        return None


class _DummyContext:
    async def cookies(self):
        return [{"name": "a", "value": "b", "domain": ".example.com", "path": "/"}]

    async def add_cookies(self, cookies):
        return None

    async def close(self):
        return None


class _DummyBrowser:
    async def close(self):
        return None


def test_wait_loop_bailout_payload_deterministic():
    agent = BrowserAgent(api_key="x", model_name="MiniMax-M2.7")
    agent.page = _DummyPage("https://example.com")
    agent._browser_engine = "chromium"

    async def _fake_ss():
        return "base64"

    agent._take_screenshot = _fake_ss

    step = asyncio.run(
        agent._build_wait_loop_bailout_step(
            step_num=7,
            wait_count=3,
            exec_ms=123,
            page_url="https://example.com",
            page_title_val="Example",
        )
    )

    assert step["action"] == "done"
    assert step["status"] == "completed"
    assert "3 consecutive wait() attempts" in step["argument"]
    assert "CAPTCHA loop detected" in step["ai_reasoning"]
    assert step["screenshot"] == "base64"


def test_escalate_switch_engine_renavigates_saved_target(monkeypatch):
    agent = BrowserAgent(api_key="x", model_name="MiniMax-M2.7")
    agent.page = _DummyPage("https://target.example/path")
    agent.context = _DummyContext()
    agent.browser = _DummyBrowser()
    agent._camoufox_ctx = None
    agent._nodriver_bridge = None

    calls = {"init": 0, "goto": []}

    async def _fake_init_browser():
        calls["init"] += 1
        agent.page = _DummyPage("about:blank")
        agent.context = _DummyContext()

    agent._init_browser = _fake_init_browser

    old = os.environ.get("BROWSER_ENGINE")
    try:
        ok = asyncio.run(agent._escalate_switch_engine("camoufox"))
        assert ok is True
        assert calls["init"] == 1
        assert agent.page.url == "https://target.example/path"
    finally:
        if old is None:
            os.environ.pop("BROWSER_ENGINE", None)
        else:
            os.environ["BROWSER_ENGINE"] = old


def test_escalate_unblocker_proxy_renavigates_saved_target(monkeypatch):
    agent = BrowserAgent(api_key="x", model_name="MiniMax-M2.7")
    agent.page = _DummyPage("https://blocked.example/hotels")
    agent.context = _DummyContext()
    agent.browser = _DummyBrowser()

    async def _fake_init_browser():
        agent.page = _DummyPage("about:blank")
        agent.context = _DummyContext()

    agent._init_browser = _fake_init_browser

    old_zone = os.environ.get("BRIGHTDATA_ZONE")
    os.environ["BRIGHTDATA_ZONE"] = "dummy-zone"
    try:
        ok = asyncio.run(agent._escalate_unblocker_proxy())
        assert ok is True
        assert agent.page.url == "https://blocked.example/hotels"
    finally:
        if old_zone is None:
            os.environ.pop("BRIGHTDATA_ZONE", None)
        else:
            os.environ["BRIGHTDATA_ZONE"] = old_zone
