import logging
logger = logging.getLogger(__name__)
"""Agent Browser - FastAPI Backend"""
import os
import json
import asyncio
import base64
from datetime import datetime
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from browser_agent import BrowserAgent

# Lifespan
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 Agent Browser API starting...")
    yield
    logger.info("👋 Agent Browser API shutting down...")

app = FastAPI(title="Agent Browser API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class TaskRequest(BaseModel):
    url: str
    task: str
    mode: str = "fast"

class TaskResponse(BaseModel):
    session_id: str
    status: str
    answer: Optional[str] = None
    steps_executed: int = 0
    steps_failed: int = 0
    screenshot: Optional[str] = None

@app.get("/api/health")
async def health():
    return {"status": "ok", "time": datetime.now().isoformat()}

@app.post("/api/execute", response_model=TaskResponse)
async def execute_task(req: TaskRequest):
    """Execute a browser task"""
    session_id = f"session_{int(datetime.now().timestamp())}"
    agent = BrowserAgent()
    
    try:
        result = await agent.execute(
            task=req.task,
            url=req.url,
            mode=req.mode
        )
        
        return TaskResponse(
            session_id=session_id,
            status="completed",
            answer=result.get("answer"),
            steps_executed=result.get("steps_executed", 0),
            steps_failed=result.get("steps_failed", 0),
            screenshot=result.get("screenshot")
        )
    except Exception as e:
        return TaskResponse(
            session_id=session_id,
            status="failed",
            answer=f"Error: {str(e)}",
            steps_failed=1
        )
    finally:
        await agent.cleanup()

@app.websocket("/ws/agent")
async def websocket_agent(ws: WebSocket):
    """WebSocket for real-time agent interaction"""
    await ws.accept()
    agent = BrowserAgent()
    
    try:
        while True:
            data = await ws.receive_json()
            task = data.get("task", "")
            url = data.get("url", "https://example.com")
            mode = data.get("mode", "fast")
            
            if not task:
                await ws.send_json({"step": 0, "action": "error", "error": "No task provided", "status": "failed"})
                continue
            
            async for step in agent.stream_execute(task, url, mode):
                await ws.send_json(step)
                
    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await ws.send_json({"step": 0, "action": "error", "error": str(e), "status": "failed"})
        except:
            pass
    finally:
        await agent.cleanup()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)