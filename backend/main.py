import logging
logger = logging.getLogger(__name__)
"""Agent Browser - FastAPI Backend"""
import os
from dotenv import load_dotenv
load_dotenv()

import json
import asyncio
import base64
import time
from datetime import datetime, timedelta
from typing import Optional
from contextlib import asynccontextmanager
from collections import defaultdict

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from browser_agent import BrowserAgent

# ─── In-memory session store ─────────────────────────────────────────────────
_sessions: dict[str, dict] = {}
_session_locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)


def _create_session(session_id: str, task: str, url: str, mode: str) -> dict:
    now = datetime.utcnow()
    return {
        "id": session_id,
        "created_at": now.isoformat(),
        "task": task,
        "url": url,
        "mode": mode,
        "status": "running",  # running | completed | failed | stopped
        "steps": [],
        "steps_count": 0,
        "failed_count": 0,
        "final_answer": None,
        "error": None,
        "started_at": now.isoformat(),
        "completed_at": None,
    }


def _update_session(session_id: str, step_data: dict):
    """Update session with step data. Safe to call from async context."""
    if session_id not in _sessions:
        return
    session = _sessions[session_id]
    step_num = step_data.get("step", 0)
    status = step_data.get("status", "")
    action = step_data.get("action", "")

    # Deduplicate: skip if this exact step was already added
    if any(s.get("step") == step_num and s.get("status") == "thinking" for s in session["steps"][-2:]):
        # Replace the thinking step with the actual result
        session["steps"][-1] = step_data
    else:
        session["steps"].append(step_data)

    session["steps_count"] = max(session["steps_count"], step_num)

    if status in ("retrying", "failed"):
        session["failed_count"] += 1
    if action == "error":
        session["status"] = "failed"
        session["error"] = step_data.get("error", "Unknown error")
        session["completed_at"] = datetime.utcnow().isoformat()
    elif action == "done" or status == "failed":
        session["status"] = "completed" if status != "failed" else "failed"
        session["final_answer"] = step_data.get("answer") or step_data.get("argument", "")
        session["completed_at"] = datetime.utcnow().isoformat()


def _cleanup_old_sessions(max_age_hours: int = 24):
    cutoff = datetime.utcnow() - timedelta(hours=max_age_hours)
    for sid in list(_sessions.keys()):
        try:
            created = datetime.fromisoformat(_sessions[sid]["created_at"])
            if created < cutoff:
                del _sessions[sid]
                if sid in _session_locks:
                    del _session_locks[sid]
        except Exception:
            pass


async def _periodic_cleanup():
    while True:
        await asyncio.sleep(1800)
        _cleanup_old_sessions()


# ─── Lifespan ────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 Agent Browser API starting...")
    cleanup_task = asyncio.create_task(_periodic_cleanup())
    yield
    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass
    logger.info("👋 Agent Browser API shutting down...")


app = FastAPI(title="Agent Browser API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Models ─────────────────────────────────────────────────────────────────
class TaskRequest(BaseModel):
    url: str
    task: str
    mode: str = "fast"
    api_key: Optional[str] = None
    model_name: Optional[str] = None


class TaskResponse(BaseModel):
    session_id: str
    status: str
    answer: Optional[str] = None
    steps_executed: int = 0
    steps_failed: int = 0
    screenshot: Optional[str] = None


# ─── REST Endpoints ──────────────────────────────────────────────────────────
@app.get("/api/health")
async def health():
    return {"status": "ok", "time": datetime.utcnow().isoformat()}


@app.get("/api/sessions")
async def list_sessions(limit: int = 50, status: Optional[str] = None):
    """List recent sessions. Optionally filter by status: running|completed|failed."""
    all_sessions = list(_sessions.values())
    # Sort by created_at desc
    all_sessions.sort(key=lambda s: s["created_at"], reverse=True)
    if status:
        all_sessions = [s for s in all_sessions if s["status"] == status]
    sessions = all_sessions[:limit]
    # Strip steps from list view to keep response small
    return {
        "total": len(sessions),
        "sessions": [
            {
                "id": s["id"],
                "task": s["task"],
                "url": s["url"],
                "mode": s["mode"],
                "status": s["status"],
                "steps_count": s["steps_count"],
                "failed_count": s["failed_count"],
                "created_at": s["created_at"],
                "completed_at": s["completed_at"],
            }
            for s in sessions
        ],
    }


@app.get("/api/sessions/{session_id}")
async def get_session(session_id: str):
    """Get full session detail including all steps."""
    if session_id not in _sessions:
        return JSONResponse(status_code=404, content={"error": "Session not found"})
    return _sessions[session_id]


@app.post("/api/execute", response_model=TaskResponse)
async def execute_task(req: TaskRequest):
    """Execute a browser task (non-streaming)."""
    session_id = f"session_{int(datetime.utcnow().timestamp())}"
    agent = BrowserAgent(api_key=req.api_key, model_name=req.model_name)
    _sessions[session_id] = _create_session(session_id, req.task, req.url, req.mode)

    try:
        import logging as _log
        steps_executed = 0
        steps_failed = 0
        answer = None
        screenshot = None

        async for step in agent.stream_execute(task=req.task, url=req.url, mode=req.mode):
            _log.error(f"[STREAM_STEP] {json.dumps({k:v for k,v in step.items() if k != 'screenshot'})}")
            _update_session(session_id, step)
            if step.get("action") == "done" and step.get("status") == "completed":
                answer = step.get("answer")
                screenshot = step.get("screenshot")
                steps_executed += 1
            elif step.get("status") == "completed":
                steps_executed += 1
                if step.get("screenshot"):
                    screenshot = step["screenshot"]
            elif step.get("status") in ("retrying", "failed"):
                steps_failed += 1

        return TaskResponse(
            session_id=session_id,
            status="completed",
            answer=answer or "Task completed",
            steps_executed=steps_executed,
            steps_failed=steps_failed,
            screenshot=screenshot,
        )
    except Exception as e:
        return TaskResponse(
            session_id=session_id,
            status="failed",
            answer=f"Error: {str(e)}",
            steps_failed=1,
        )
    finally:
        await agent.cleanup()


# ─── WebSocket Endpoint ──────────────────────────────────────────────────────
@app.websocket("/ws/agent")
async def websocket_agent(ws: WebSocket):
    """WebSocket for real-time agent interaction. Sessions are tracked server-side."""
    await ws.accept(max_size=10_000_000)
    agent = None
    current_session_id = None

    try:
        while True:
            data = await ws.receive_json()
            task = data.get("task", "")
            url = data.get("url", "https://example.com")
            mode = data.get("mode", "fast")
            incoming_key = data.get("api_key")
            incoming_model = data.get("model_name")

            # Recreate agent if credentials changed
            if incoming_key is not None or incoming_model is not None:
                if agent is None or agent.api_key != incoming_key or agent.model_name != incoming_model:
                    if agent:
                        await agent.cleanup()
                    agent = BrowserAgent(api_key=incoming_key, model_name=incoming_model)
            else:
                if agent is None:
                    agent = BrowserAgent()

            if not task:
                await ws.send_json({"step": 0, "action": "error", "error": "No task provided", "status": "failed"})
                continue

            # Create session
            current_session_id = f"session_{int(datetime.utcnow().timestamp())}"
            _sessions[current_session_id] = _create_session(current_session_id, task, url, mode)

            async for step in agent.stream_execute(task, url, mode):
                _update_session(current_session_id, step)
                await ws.send_json(step)

    except WebSocketDisconnect:
        # Mark session as stopped if it was running
        if current_session_id and current_session_id in _sessions:
            if _sessions[current_session_id]["status"] == "running":
                _sessions[current_session_id]["status"] = "stopped"
                _sessions[current_session_id]["completed_at"] = datetime.utcnow().isoformat()
    except Exception as e:
        try:
            await ws.send_json({"step": 0, "action": "error", "error": str(e), "status": "failed"})
        except Exception:
            pass
    finally:
        if agent:
            await agent.cleanup()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
