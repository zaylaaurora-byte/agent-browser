"""Agent Browser - AI-powered browser automation"""
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
import redis.asyncio as redis
from celery import Celery

from browser_agent import BrowserAgent

# Redis
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
celery_app = Celery("agent-browser", broker=REDIS_URL, backend=REDIS_URL)

# In-memory session store (will use Redis in prod)
sessions: dict = {}

class TaskRequest(BaseModel):
    url: str
    task: str
    mode: str = "fast"  # fast or stealth

class TaskResponse(BaseModel):
    session_id: str
    status: str
    answer: Optional[str] = None
    steps_executed: int = 0
    steps_failed: int = 0
    screenshot: Optional[str] = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await redis.from_url(REDIS_URL, decode_responses=True)
    yield
    # Shutdown
    pass

app = FastAPI(title="Agent Browser API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Browser agent instance
agent = BrowserAgent()

@app.post("/api/execute", response_model=TaskResponse)
async def execute_task(req: TaskRequest):
    """Execute a browser task"""
    session_id = f"session_{datetime.now().timestamp()}"
    
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
            answer=str(e)
        )

@app.websocket("/ws/agent")
async def websocket_agent(ws: WebSocket):
    """WebSocket for real-time agent interaction"""
    await ws.accept()
    
    try:
        while True:
            data = await ws.receive_json()
            task = data.get("task")
            url = data.get("url", "https://example.com")
            mode = data.get("mode", "fast")
            
            # Stream steps
            async for step in agent.stream_execute(task, url, mode):
                await ws.send_json(step)
                
    except WebSocketDisconnect:
        pass

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)