from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]


def test_frontend_step_type_has_ctrl_field():
    types_ts = (ROOT / "src/components/agent/types.ts").read_text()
    assert 'ctrl?: "pause" | "resume" | "stop";' in types_ts


def test_activity_feed_uses_shared_step_type():
    feed_tsx = (ROOT / "src/components/activity-feed.tsx").read_text()
    assert 'import type { Step } from "@/components/agent/types";' in feed_tsx
    assert "interface Step {" not in feed_tsx


def test_backend_ws_echoes_ctrl_on_step_payload():
    main_py = (ROOT / "backend/main.py").read_text()
    assert 'if ctrl in ("pause", "resume", "stop"):' in main_py
    assert 'step["ctrl"] = applied_ctrl' in main_py


def test_backend_stream_payload_contains_core_fields():
    agent_py = (ROOT / "backend/browser_agent.py").read_text()

    # Ensure at least one representative step payload includes these core fields.
    required_literals = [
        '"step": step_num',
        '"action": action',
        '"status":',
        '"url": self.page.url',
        '"page_title": page_title',
        '"duration_ms":',
        '"model":',
    ]
    for lit in required_literals:
        assert lit in agent_py

    # Guard against accidental removal of thinking/observation from stream payloads.
    assert '"thinking":' in agent_py
    assert '"observation":' in agent_py
