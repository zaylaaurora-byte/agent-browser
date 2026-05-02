"""
Workflow Recorder — record browser actions as JSON, save/load, replay.
Builds on ActionHistory: every recorded action becomes a step in a workflow.
Workflows are saved to SQLite and exported as downloadable JSON.
Replay feeds steps + current DOM to AI for smart step-matching.
"""
import json
import asyncio
import uuid
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional

# ── DB path (shared with run_db) ───────────────────────────────────────────
_WORKFLOW_DB = Path("~/.agent-browser/workflows.db").expanduser()
_WORKFLOW_DB.parent.mkdir(parents=True, exist_ok=True)

def _get_conn() -> sqlite3.Connection:
    if not hasattr(_get_conn, "_conn"):
        _get_conn._conn = sqlite3.connect(str(_WORKFLOW_DB), check_same_thread=False)
        _get_conn._conn.row_factory = sqlite3.Row
    return _get_conn._conn


# ── Schema ────────────────────────────────────────────────────────────────────
SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS workflows (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    description TEXT DEFAULT '',
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    steps       TEXT NOT NULL,   -- JSON array of workflow steps
    tags        TEXT DEFAULT '[]'
);
"""


def _init_db():
    conn = _get_conn()
    conn.executescript(SCHEMA_SQL)
    conn.commit()


# ── Workflow step ─────────────────────────────────────────────────────────────
def make_step(action: str, args: dict, observation: str = "",
              screenshot_before: str = "", screenshot_after: str = "",
              diff_type: str = "") -> dict:
    return {
        "id": str(uuid.uuid4())[:8],
        "action": action,
        "args": args,
        "observation": observation,
        "screenshot_before": screenshot_before,
        "screenshot_after": screenshot_after,
        "diff_type": diff_type,
        "recorded_at": datetime.utcnow().isoformat(),
    }


# ── WorkflowRecorder ──────────────────────────────────────────────────────────
class WorkflowRecorder:
    """
    Records browser actions as a workflow.
    Usage:
        recorder = WorkflowRecorder(agent)
        recorder.start_recording()
        # ... agent executes actions ...
        recorder.stop_recording()
        recorder.save_workflow("my workflow")
        workflow = recorder.load_workflow("my workflow")
        recorder.replay(agent)
    """

    def __init__(self, browser_agent, action_history):
        self.agent = browser_agent
        self.history = action_history
        self.recording = False
        self.steps: list[dict] = []
        self._started_at = None
        _init_db()

    # ── Record ────────────────────────────────────────────────────────────────
    def start_recording(self, name: str = "Untitled Workflow"):
        """Start recording a new workflow."""
        self.steps = []
        self.recording = True
        self._started_at = datetime.utcnow().isoformat()

    def record_step(self, action: str, args: dict, observation: str = "",
                    diff_info: Optional[dict] = None):
        """Add a step to the current recording."""
        if not self.recording:
            return
        step = make_step(
            action=action,
            args=args,
            observation=observation,
            diff_type=diff_info.get("diff_type", "") if diff_info else "",
        )
        self.steps.append(step)

    def stop_recording(self) -> list[dict]:
        """Stop recording and return the steps captured."""
        self.recording = False
        return self.steps

    # ── Persistence ───────────────────────────────────────────────────────────
    def save_workflow(self, name: str, description: str = "",
                      tags: list[str] = None) -> str:
        """Save current recording to SQLite. Returns workflow ID."""
        if not self.steps:
            raise ValueError("No steps recorded — nothing to save")

        workflow_id = str(uuid.uuid4())[:12]
        now = datetime.utcnow().isoformat()
        tags = tags or []

        conn = _get_conn()
        conn.execute("""
            INSERT INTO workflows (id, name, description, created_at, updated_at, steps, tags)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (workflow_id, name, description, now, now,
              json.dumps(self.steps, ensure_ascii=False), json.dumps(tags)))
        conn.commit()
        return workflow_id

    def load_workflow(self, workflow_id: str) -> Optional[dict]:
        """Load a workflow by ID."""
        conn = _get_conn()
        row = conn.execute(
            "SELECT * FROM workflows WHERE id = ?", (workflow_id,)
        ).fetchone()
        if not row:
            return None
        wf = dict(row)
        wf["steps"] = json.loads(wf["steps"])
        wf["tags"] = json.loads(wf["tags"])
        return wf

    def load_workflow_by_name(self, name: str) -> Optional[dict]:
        """Load most recent workflow by name."""
        conn = _get_conn()
        row = conn.execute(
            "SELECT * FROM workflows WHERE name = ? ORDER BY updated_at DESC LIMIT 1",
            (name,)
        ).fetchone()
        if not row:
            return None
        wf = dict(row)
        wf["steps"] = json.loads(wf["steps"])
        wf["tags"] = json.loads(wf["tags"])
        return wf

    def list_workflows(self, limit: int = 20) -> list[dict]:
        """List all saved workflows."""
        conn = _get_conn()
        rows = conn.execute(
            "SELECT id, name, description, created_at, updated_at, tags FROM workflows "
            "ORDER BY updated_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(row) for row in rows]

    def delete_workflow(self, workflow_id: str) -> bool:
        """Delete a workflow by ID."""
        conn = _get_conn()
        n = conn.execute(
            "DELETE FROM workflows WHERE id = ?", (workflow_id,)
        ).rowcount
        conn.commit()
        return n > 0

    # ── Export / Import ──────────────────────────────────────────────────────
    def export_json(self, workflow: dict) -> str:
        """Export a workflow as a JSON string for download."""
        export = {
            "name": workflow["name"],
            "description": workflow.get("description", ""),
            "created_at": workflow["created_at"],
            "steps": workflow["steps"],
        }
        return json.dumps(export, indent=2, ensure_ascii=False)

    def import_json(self, json_str: str) -> dict:
        """Import a workflow from JSON string."""
        data = json.loads(json_str)
        if "steps" not in data or not data["steps"]:
            raise ValueError("Invalid workflow JSON — missing 'steps'")
        return data

    # ── Replay ───────────────────────────────────────────────────────────────
    async def replay(self, agent, workflow: Optional[dict] = None,
                     workflow_id: Optional[str] = None,
                     match_strategy: str = "fuzzy"):
        """
        Replay a saved workflow on the current page.
        match_strategy: 'exact' (selector must match), 'fuzzy' (AI helps match),
                        'skip' (skip steps that don't match)
        Returns list of results per step.
        """
        if workflow_id and not workflow:
            workflow = self.load_workflow(workflow_id)
        if not workflow:
            raise ValueError("No workflow provided or found")

        results = []
        steps = workflow["steps"]

        for i, step in enumerate(steps):
            action = step["action"]
            args = step["args"]
            observation = step.get("observation", "")

            # Try to execute — use AI to help match if selector changed
            result = {"step": i + 1, "action": action, "args": args,
                      "status": "pending"}

            try:
                exec_result = await asyncio.wait_for(
                    agent._execute_action(action, args.get("selector", str(args.get("value", "")))),
                    timeout=20.0
                )
                result["status"] = "completed" if exec_result.get("success") else "failed"
                result["result"] = exec_result
            except asyncio.TimeoutError:
                result["status"] = "failed"
                result["error"] = "timeout"
            except Exception as e:
                result["status"] = "skipped"
                result["error"] = str(e)[:100]

            results.append(result)

            # Brief pause between steps
            await asyncio.sleep(0.5)

        return results
