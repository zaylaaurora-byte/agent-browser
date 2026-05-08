import asyncio
import json

from fastapi.testclient import TestClient

import main
import mcp_server


REQUIRED_STEP_KEYS = {
    "step",
    "action",
    "status",
    "url",
    "page_title",
    "duration_ms",
    "model",
    "observation",
}


class DummyAgent:
    def __init__(self, api_key=None, model_name=None):
        self.api_key = api_key
        self.model_name = model_name or "MiniMax-M2.7"
        self._browser_engine = "chromium"
        self._server_sessions = {}
        self.page = None

    async def _init_browser(self):
        return None

    async def cleanup(self):
        return None

    async def _take_screenshot(self):
        return "base64"

    async def stream_execute(self, task, url, mode):
        yield {
            "step": 1,
            "action": "navigate",
            "status": "completed",
            "url": url,
            "page_title": "Dummy Page",
            "duration_ms": 12,
            "model": self.model_name,
            "observation": f"Loaded {url}",
            "screenshot": "base64",
        }
        yield {
            "step": 2,
            "action": "done",
            "argument": "done",
            "answer": "ok",
            "status": "completed",
            "url": url,
            "page_title": "Dummy Page",
            "duration_ms": 21,
            "model": self.model_name,
            "observation": "finished",
            "screenshot": "base64",
        }


def _patch_run_db(monkeypatch):
    monkeypatch.setattr(main, "create_run", lambda *a, **k: 1)
    monkeypatch.setattr(main, "add_step", lambda *a, **k: None)
    monkeypatch.setattr(main, "update_run", lambda *a, **k: None)


def test_rest_execute_step_shape_parity(monkeypatch):
    _patch_run_db(monkeypatch)
    monkeypatch.setattr(main, "BrowserAgent", DummyAgent)
    client = TestClient(main.app)

    resp = client.post(
        "/api/execute",
        json={"url": "https://example.com", "task": "test", "mode": "fast"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "completed"
    assert body["steps_executed"] >= 1
    assert "screenshot" in body


def test_ws_agent_step_shape_parity(monkeypatch):
    _patch_run_db(monkeypatch)
    monkeypatch.setattr(main, "BrowserAgent", DummyAgent)
    client = TestClient(main.app)

    with client.websocket_connect("/ws/agent") as ws:
        ws.send_json({"task": "test", "url": "https://example.com", "mode": "fast"})
        step1 = ws.receive_json()
        assert REQUIRED_STEP_KEYS.issubset(set(step1.keys()))
        step2 = ws.receive_json()
        assert step2["action"] == "done"
        assert REQUIRED_STEP_KEYS.issubset(set(step2.keys()))


def test_mcp_execute_task_session_parity(monkeypatch):
    agent = DummyAgent()

    async def _run():
        out = await mcp_server._call_execute_task(
            agent,
            {"task": "test mcp", "url": "https://example.com", "mode": "fast"},
        )
        text = out[0].text
        assert "session_id=" in text
        session_id = text.split("session_id=")[1].split("\n", 1)[0].strip()

        # Let background task append steps
        await asyncio.sleep(0.15)

        poll = await mcp_server._call_get_session(agent, {"session_id": session_id})
        poll_text = poll[0].text
        assert f"session_id={session_id}" in poll_text
        assert "status=" in poll_text
        assert "steps_executed=" in poll_text

        sess = agent._server_sessions[session_id]
        assert len(sess["steps"]) >= 1
        assert REQUIRED_STEP_KEYS.issubset(set(sess["steps"][0].keys()))

    asyncio.run(_run())
