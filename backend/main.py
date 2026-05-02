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

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from browser_agent import BrowserAgent
from mcp_server import create_mcp_server, set_agent
from credential_vault import CredentialVault, VAULT_AUDIT_FILE, _VAULT_TOKEN

vault = CredentialVault()

# ─── In-memory session store ─────────────────────────────────────────────────
_sessions: dict[str, dict] = {}
_session_locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
_active_ws_agent: Optional["BrowserAgent"] = None  # currently active WebSocket agent (Phase 2)

# ─── Supervisor state ──────────────────────────────────────────────────────────
_agent_paused = False
_agent_running_session: Optional[str] = None


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
    # Initialize MCP server with no agent — will be attached on first WebSocket connection
    create_mcp_server(None)
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


class CredentialAdd(BaseModel):
    domain: str
    username: str
    password: str
    totp_secret: Optional[str] = None
    label: Optional[str] = None


# ─── REST Endpoints ──────────────────────────────────────────────────────────
@app.get("/api/health")
async def health():
    return {"status": "ok", "time": datetime.utcnow().isoformat()}


@app.get("/api/config")
async def get_config(request: Request):
    """Return current backend configuration (non-sensitive)."""
    # Auto-detect accessible URL from Host header (works for mobile on LAN)
    host = request.headers.get("host", "localhost:8001")
    scheme = request.headers.get("x-forwarded-proto", "http")
    backend_url = f"{scheme}://{host}"
    return {
        "model_name": os.getenv("AI_MODEL", "MiniMax-M2.7"),
        "max_steps": {"fast": 12, "standard": 20, "deep": 30},
        "version": "1.0.0",
        "backend_url": backend_url,
        "ws_url": backend_url.replace("http", "ws") + "/ws/agent",
    }


class TestModelRequest(BaseModel):
    provider: str
    api_key: Optional[str] = None
    model_name: str
    base_url: Optional[str] = None  # for Ollama


@app.post("/api/test-model")
async def test_model(req: TestModelRequest):
    """Send a tiny test prompt to verify the model API credentials work."""
    import httpx
    test_prompt = "Reply with exactly one word: hello"
    start = time.time()
    latency_ms = None
    error = None
    response_text = None

    try:
        if req.provider == "ollama":
            base = (req.base_url or "http://localhost:11434").rstrip("/")
            async with httpx.AsyncClient(timeout=30.0) as client:
                r = await client.post(
                    f"{base}/api/generate",
                    json={"model": req.model_name, "prompt": test_prompt, "stream": False},
                )
                r.raise_for_status()
                data = r.json()
                response_text = data.get("response", "").strip()
        elif req.provider == "openai":
            async with httpx.AsyncClient(timeout=30.0) as client:
                r = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {req.api_key}"},
                    json={
                        "model": req.model_name,
                        "messages": [{"role": "user", "content": test_prompt}],
                        "max_tokens": 10,
                    },
                )
                r.raise_for_status()
                data = r.json()
                response_text = data["choices"][0]["message"]["content"].strip()
        elif req.provider == "anthropic":
            async with httpx.AsyncClient(timeout=30.0) as client:
                r = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": req.api_key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json",
                    },
                    json={
                        "model": req.model_name,
                        "messages": [{"role": "user", "content": test_prompt}],
                        "max_tokens": 10,
                    },
                )
                r.raise_for_status()
                data = r.json()
                response_text = data["content"][0]["text"].strip()
        elif req.provider == "minimax":
            async with httpx.AsyncClient(timeout=30.0) as client:
                r = await client.post(
                    "https://api.minimax.chat/v1/text/chatcompletion_v2",
                    headers={"Authorization": f"Bearer {req.api_key}"},
                    json={
                        "model": req.model_name,
                        "messages": [{"role": "user", "content": test_prompt}],
                        "max_tokens": 10,
                    },
                )
                r.raise_for_status()
                data = r.json()
                response_text = data["choices"][0]["message"]["content"].strip()
        latency_ms = round((time.time() - start) * 1000)
    except httpx.TimeoutException:
        error = "Request timed out after 30s"
    except httpx.HTTPStatusError as e:
        error = f"HTTP {e.response.status_code}: {e.response.text[:200]}"
    except Exception as e:
        error = str(e)[:200]

    return {
        "ok": error is None,
        "latency_ms": latency_ms,
        "response": response_text,
        "error": error,
    }


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


@app.post("/api/sessions/{session_id}/stop")
async def stop_session(session_id: str):
    """Stop a running session gracefully (marks as stopped, doesn't kill browser)."""
    if session_id not in _sessions:
        return JSONResponse(status_code=404, content={"error": "Session not found"})
    session = _sessions[session_id]
    if session["status"] not in ("running", "paused"):
        return JSONResponse(status_code=400, content={"error": f"Session is not running (status: {session['status']})"})
    session["status"] = "stopped"
    session["completed_at"] = datetime.utcnow().isoformat()
    return {"ok": True, "session_id": session_id, "status": "stopped"}


@app.delete("/api/sessions/{session_id}")
async def delete_session(session_id: str):
    """Delete a session and free its resources."""
    if session_id not in _sessions:
        return JSONResponse(status_code=404, content={"error": "Session not found"})
    session = _sessions.pop(session_id)
    # Release the session lock if held
    if session_id in _session_locks:
        del _session_locks[session_id]
    return {"ok": True, "session_id": session_id}


@app.get("/api/metrics")
async def get_metrics():
    """Return runtime metrics: session counts, engine stats, uptime."""
    import time
    now = datetime.utcnow()
    running = sum(1 for s in _sessions.values() if s["status"] == "running")
    completed = sum(1 for s in _sessions.values() if s["status"] == "completed")
    failed = sum(1 for s in _sessions.values() if s["status"] == "failed")
    stopped = sum(1 for s in _sessions.values() if s["status"] in ("stopped", "paused"))

    # Browser engine from active WS agent if any
    engine = getattr(_active_ws_agent, "_browser_engine", None) if _active_ws_agent else None

    return {
        "sessions": {
            "total": len(_sessions),
            "running": running,
            "completed": completed,
            "failed": failed,
            "stopped": stopped,
        },
        "engine": engine or "no active session",
        "uptime_since": getattr(get_metrics, "_start_time", now).isoformat(),
    }


# ─── Named Session Persistence Endpoints (Phase 2) ──────────────────────────
@app.get("/api/persistent-sessions")
async def list_persistent_sessions():
    """List all saved browser sessions (cookies, localStorage, viewport, proxy, UA)."""
    from session_manager import SessionManager
    # Dummy agent just for listing
    class DummyAgent:
        session_manager = None
    mgr = SessionManager.__new__(SessionManager)
    mgr.active_session_name = None
    sessions = mgr.list_sessions()
    return {"sessions": sessions}


@app.post("/api/persistent-sessions/{name}/save")
async def save_persistent_session(name: str):
    """Save current browser state as a named persistent session."""
    if _active_ws_agent is None:
        return JSONResponse(status_code=400, content={"error": "No active browser session. Use WebSocket to start a session first."})
    result = await _active_ws_agent.save_session(name)
    return result


@app.post("/api/persistent-sessions/{name}/load")
async def load_persistent_session(name: str):
    """Load a named persistent session into the current browser."""
    if _active_ws_agent is None:
        return JSONResponse(status_code=400, content={"error": "No active browser session. Use WebSocket to start a session first."})
    result = await _active_ws_agent.load_session(name)
    if "error" in result:
        return JSONResponse(status_code=404, content=result)
    return result


@app.delete("/api/persistent-sessions/{name}")
async def delete_persistent_session(name: str):
    """Delete a named persistent session."""
    from session_manager import SessionManager
    class DummyAgent:
        session_manager = None
    mgr = SessionManager.__new__(SessionManager)
    mgr.active_session_name = None
    result = mgr.delete_session(name)
    return result


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


# ─── Supervisor Endpoints ───────────────────────────────────────────────────────
@app.post("/api/supervisor/pause")
async def pause_agent():
    """Pause the currently running agent (stops after current step)."""
    global _agent_paused
    _agent_paused = True
    return {"paused": True}


@app.post("/api/supervisor/resume")
async def resume_agent():
    """Resume a paused agent."""
    global _agent_paused
    _agent_paused = False
    return {"resumed": True}


@app.get("/api/supervisor/status")
async def agent_status():
    """Get current agent state."""
    return {"paused": _agent_paused, "session": _agent_running_session}


@app.post("/api/history/undo")
async def undo_last_action():
    """Undo the last undoable browser action."""
    if _active_ws_agent and hasattr(_active_ws_agent, 'action_history'):
        return await _active_ws_agent.undo_last_action()
    return {"error": "No active agent"}


@app.get("/api/history")
async def get_action_history(limit: int = 50):
    """Get action history (last N actions)."""
    if _active_ws_agent and hasattr(_active_ws_agent, 'action_history'):
        return {"history": _active_ws_agent.action_history.get_history(limit)}
    return {"history": []}


@app.get("/api/history/snapshot")
async def get_last_snapshot():
    """Get the most recent undo snapshot."""
    if _active_ws_agent and hasattr(_active_ws_agent, 'action_history'):
        snap = _active_ws_agent.action_history.get_last_snapshot()
        return snap if snap else {"error": "No snapshot"}
    return {"error": "No active agent"}


# ─── Credential Vault Endpoints (Phase 5) ─────────────────────────────────────
@app.get("/api/vault/domains")
async def list_vault_domains():
    """List all domains with stored credentials."""
    return {"domains": vault.list_domains()}


@app.get("/api/vault/credential/{domain}")
async def get_vault_credential(domain: str):
    """Get credential metadata (without password) for a domain. Returns labels/usernames only."""
    return vault.get_credential(domain)


@app.post("/api/vault/credential")
async def add_vault_credential(cred: CredentialAdd):
    """Add a credential for a domain."""
    return vault.add_credential(cred.domain, cred.username, cred.password, cred.totp_secret, cred.label)


@app.post("/api/vault/fill/{domain}")
async def fill_vault_credential(domain: str, request: Request):
    """
    Blind fill — returns actual credential for page form injection.
    NEVER returns password to AI — only to the form filler.
    Requires X-Vault-Token header for authentication.
    """
    token = request.headers.get("x-vault-token", "")
    if token != _VAULT_TOKEN:
        return JSONResponse(status_code=401, content={"error": "Unauthorized"})
    return vault.fill_credential(domain)


@app.delete("/api/vault/credential/{credential_id}")
async def delete_vault_credential(credential_id: str):
    """Delete a credential by ID."""
    return vault.delete_credential(credential_id)


@app.get("/api/vault/audit")
async def get_vault_audit():
    """Get the last 50 audit log entries."""
    if not VAULT_AUDIT_FILE.exists():
        return {"audit": []}
    return {"audit": VAULT_AUDIT_FILE.read_text().splitlines()[-50:]}


# ─── MCP HTTP/SSE Endpoints (Phase 4) ───────────────────────────────────────
# These expose the same browser control tools over HTTP+SSE so Hermes Agent
# and other HTTP-based MCP clients can drive the browser.

@app.get("/mcp")
async def mcp_sse(request: Request):
    """
    SSE stream for long-lived MCP tool sessions.
    GET /mcp upgrades to an SSE connection that receives tool results.
    POST /mcp accepts one-shot tool calls and returns results immediately.
    """
    from fastapi.responses import JSONResponse
    from sse_starlette.sse import EventSourceResponse

    # One-shot tool call via query params or POST body
    tool_name = request.query_params.get("tool")
    if tool_name:
        args_str = request.query_params.get("args", "{}")
        try:
            import json as _json
            arguments = _json.loads(args_str) if args_str != "{}" else {}
        except Exception:
            arguments = {}

        if _active_ws_agent is None:
            return JSONResponse(
                status_code=400,
                content={"error": "No active browser session. Start one via the WebSocket endpoint first."},
            )

        from mcp_server import _TOOL_HANDLERS
        handler = _TOOL_HANDLERS.get(tool_name)
        if handler is None:
            return JSONResponse(status_code=400, content={"error": f"Unknown tool: {tool_name}"})

        try:
            results = await handler(_active_ws_agent, arguments)
            # Convert TextContent to dict
            content = [{"type": r.type, "text": r.text} for r in results]
            return JSONResponse(content={"results": content})
        except Exception as e:
            return JSONResponse(status_code=500, content={"error": str(e)})

    # Long-lived SSE connection — send periodic pings
    async def event_puller():
        import asyncio as _asyncio
        while True:
            yield {"event": "ping", "data": "connected"}
            await _asyncio.sleep(30)

    return EventSourceResponse(event_puller())


@app.post("/mcp")
async def mcp_post(request: Request):
    """One-shot MCP tool call over HTTP POST."""
    from fastapi.responses import JSONResponse

    try:
        body = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"error": "Invalid JSON body"})

    tool_name = body.get("tool")
    arguments = body.get("arguments", {})

    if not tool_name:
        return JSONResponse(status_code=400, content={"error": "Missing 'tool' field"})

    if _active_ws_agent is None:
        return JSONResponse(
            status_code=400,
            content={"error": "No active browser session. Start one via the WebSocket endpoint first."},
        )

    from mcp_server import _TOOL_HANDLERS
    handler = _TOOL_HANDLERS.get(tool_name)
    if handler is None:
        return JSONResponse(status_code=400, content={"error": f"Unknown tool: {tool_name}"})

    try:
        results = await handler(_active_ws_agent, arguments)
        content = [{"type": r.type, "text": r.text} for r in results]
        return JSONResponse(content={"results": content})
    except Exception as e:
        logger.error(f"MCP tool {tool_name} failed: {e}", exc_info=True)
        return JSONResponse(status_code=500, content={"error": str(e)})


# ─── WebSocket Endpoint ──────────────────────────────────────────────────────
@app.websocket("/ws/agent")
async def websocket_agent(ws: WebSocket):
    """WebSocket for real-time agent interaction. Sessions are tracked server-side."""
    await ws.accept()
    global _active_ws_agent
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
                    _active_ws_agent = agent
                    set_agent(agent)
            else:
                if agent is None:
                    agent = BrowserAgent()
                    _active_ws_agent = agent
                    set_agent(agent)

            if not task:
                await ws.send_json({"step": 0, "action": "error", "error": "No task provided", "status": "failed"})
                continue

            # Create session
            current_session_id = f"session_{int(datetime.utcnow().timestamp())}"
            _sessions[current_session_id] = _create_session(current_session_id, task, url, mode)

            global _agent_running_session
            _agent_running_session = current_session_id

            async for step in agent.stream_execute(task, url, mode):
                _update_session(current_session_id, step)
                await ws.send_json(step)
                # Check pause signal — yield a paused step and stop iteration
                if _agent_paused:
                    paused_step = {
                        "step": step.get("step", 0) + 1,
                        "action": "paused",
                        "status": "paused",
                        "observation": "Agent paused by supervisor",
                        "timestamp": datetime.utcnow().timestamp(),
                    }
                    _update_session(current_session_id, paused_step)
                    await ws.send_json(paused_step)
                    break

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
        _active_ws_agent = None
        _agent_running_session = None


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
