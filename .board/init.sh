#!/bin/bash
# init.sh — project health check for agent-browser
set -e
echo "[init] Checking agent-browser project health..."

cd ~/Projects/agent-browser/backend

# Check venv exists
if [ ! -d "venv" ]; then
    echo "[init] ERROR: venv not found at backend/venv"
    exit 1
fi

# Activate venv and check critical imports
source venv/bin/activate
python3 -c "import camoufox; import httpx; import playwright" 2>&1
echo "[init] Core dependencies OK"

# Check browser_agent.py compiles
python3 -m py_compile browser_agent.py
echo "[init] browser_agent.py compiles OK"

# Check main.py compiles
python3 -m py_compile main.py
echo "[init] main.py compiles OK"

# Quick browser init test (camoufox-virtual)
python3 -c "
import asyncio
from browser_agent import BrowserAgent
async def test():
    agent = BrowserAgent()
    await agent._init_browser()
    print('Engine:', agent._browser_engine)
    await agent.cleanup()
asyncio.run(test())
" 2>&1
echo "[init] Browser launch OK"

# Check Docker config
cd ~/Projects/agent-browser
if [ -f "docker-compose.yml" ]; then
    grep -q "8001" docker-compose.yml && echo "[init] Docker port config OK" || echo "[init] WARN: Docker port not 8001"
fi

echo "[init] Health check passed"
exit 0
