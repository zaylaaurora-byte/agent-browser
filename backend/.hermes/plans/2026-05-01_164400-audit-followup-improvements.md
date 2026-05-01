# Plan: agent-browser audit follow-up improvements

## Goal

Fix the 2 remaining audit findings from the multi-agent code audit, plus add useful missing endpoints.

---

## Current Context

**Backend:** `/home/zayla/Projects/agent-browser/backend/`
**Server:** Running on port 8004 (from previous fixes)
**Status:** 5/7 critical-high issues resolved. 2 pending.

### Pending Issues

| ID | Priority | Issue | File |
|----|----------|-------|------|
| `arch1` | Medium | `fill_from_vault` uses blocking sync `requests` inside async method | `browser_agent.py` |
| `arch2` | Low | Missing endpoints: `DELETE /api/sessions/{id}`, `GET /api/metrics`, `POST /api/sessions/{id}/stop` | `main.py` |

---

## Step 1: Fix `fill_from_vault` sync blocking call

### Problem
```python
# browser_agent.py — inside async def fill_from_vault()
import requests
resp = requests.post(f"http://localhost:8001/api/vault/fill/{domain}")  # BLOCKS event loop
```
`requests` is synchronous — blocks the entire asyncio event loop for the duration of the HTTP call. Under load this will freeze all concurrent browser operations.

### Fix
Replace with `httpx.AsyncClient` (already in the venv as a dependency of FastAPI/Starlette):

```python
async def fill_from_vault(self, domain: str):
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"http://{self.backend_host}/api/vault/fill/{domain}",
            headers={"x-vault-token": self._get_vault_token()}
        )
        ...
```

**Changes:**
- `browser_agent.py` — replace `import requests` + `requests.post()` with `httpx.AsyncClient` + `await client.post()`
- `browser_agent.py` — add `_get_vault_token()` helper that reads `VAULT_API_TOKEN` from env (same token used by `credential_vault.py`)
- `browser_agent.py` — store `backend_host` on `__init__` (already available from config, pass through from `__init__`)

**Verification:**
```bash
curl -s -X POST http://localhost:8004/api/vault/fill/google -H "x-vault-token: agent-browser-internal-dev-token"
# Should return 401 if no credential exists, not crash
```

---

## Step 2: Add missing REST endpoints to `main.py`

### A. `DELETE /api/sessions/{session_id}`

Delete an in-memory session immediately (currently only auto-expires after 24h).

```python
@app.delete("/api/sessions/{session_id}")
async def delete_session(session_id: str):
    """Delete an in-memory session."""
    if session_id not in _sessions:
        return JSONResponse(status_code=404, content={"error": "Session not found"})
    del _sessions[session_id]
    return {"deleted": True, "id": session_id}
```

### B. `POST /api/sessions/{session_id}/stop`

Cancel a running WebSocket session mid-execution. Requires storing an `asyncio.cancel` handle per session.

**Approach:** Store a `dict[str, asyncio.Task]` mapping `session_id → task` when `stream_execute` is called. The stop endpoint calls `.cancel()` on the task.

```python
_session_tasks: dict[str, asyncio.Task] = {}

# In websocket_agent, wrap stream_execute:
task = asyncio.create_task(_run_session(current_session_id, agent, task, url, mode))
_session_tasks[current_session_id] = task

@app.post("/api/sessions/{session_id}/stop")
async def stop_session(session_id: str):
    task = _session_tasks.get(session_id)
    if task is None:
        return JSONResponse(status_code=404, content={"error": "Session not found or already complete"})
    task.cancel()
    if session_id in _sessions:
        _sessions[session_id]["status"] = "stopped"
        _sessions[session_id]["completed_at"] = datetime.utcnow().isoformat()
    return {"stopped": True, "id": session_id}
```

### C. `GET /api/metrics`

Lightweight JSON metrics endpoint for monitoring.

```python
@app.get("/api/metrics")
async def get_metrics():
    sessions = list(_sessions.values())
    total = len(sessions)
    completed = sum(1 for s in sessions if s["status"] == "completed")
    failed = sum(1 for s in sessions if s["status"] == "failed")
    running = sum(1 for s in sessions if s["status"] == "running")
    return {
        "sessions_total": total,
        "sessions_completed": completed,
        "sessions_failed": failed,
        "sessions_running": running,
        "active_ws_agent": _active_ws_agent is not None,
        "agent_paused": _agent_paused,
        "uptime": datetime.utcnow().isoformat(),
    }
```

---

## Files to Change

| File | Change |
|------|--------|
| `browser_agent.py` | Replace `requests` with `httpx.AsyncClient` in `fill_from_vault`; add `_get_vault_token()` |
| `main.py` | Add `DELETE /api/sessions/{id}`, `POST /api/sessions/{id}/stop`, `GET /api/metrics`; add `_session_tasks` dict; wrap WS handler in task |

---

## Validation

1. `python3 -c "from browser_agent import BrowserAgent; print('browser_agent OK')"`
2. `python3 -c "import main; print('main OK')"`
3. Restart server on new port, run:
   - `DELETE /api/sessions/nonexistent` → 404
   - `POST /api/sessions/test/stop` → 404 (no such session)
   - `GET /api/metrics` → JSON with session counts
   - `GET /api/vault/fill/test` (no token) → 401

---

## Risks / Tradeoffs

- **Task cancellation in asyncio:** `.cancel()` on a task doesn't guarantee immediate stop — the `CancelledError` propagates at the next `await`. Acceptable for this use case.
- **httpx dependency:** Already present via FastAPI/Starlette. No new deps needed.
- **`_session_tasks` memory:** Tasks are cleaned up in `finally` block of the WebSocket handler when session ends. No persistent leak risk.
