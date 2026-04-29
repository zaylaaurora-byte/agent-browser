"""Browser Agent - AI-controlled browser automation with stealth"""
import asyncio
import os
import json
import base64
from typing import AsyncGenerator, Optional
from datetime import datetime

from playwright.async_api import async_playwright, Browser, Page, Playwright

# Stealth browser arguments
STEALTH_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--disable-dev-shm-usage",
    "--no-sandbox",
    "--disable-setuid-sandbox",
    "--disable-web-security",
    "--disable-features=IsolateOrigins,site-per-process",
    "--window-size=1920,1080",
    "--start-maximized",
]

# Anti-detection configs
STEALTH_CONFIG = {
    "webgl_vendor": "Intel Inc.",
    "webgl_renderer": "Intel Iris OpenGL VK",
    "hardware_concurrency": 8,
    "device_memory": 8,
    "platform": "Linux x86_64",
    "languages": ["en-US", "en"],
    "timezone": "America/New_York",
}

PROMPT_TEMPLATE = """You are a browser automation agent. Given a task and current page state, decide what action to take.

Current page:
- URL: {url}
- Title: {title}

Page content summary:
{summary}

Task: {task}

Available actions:
1. navigate(url) - Go to a URL
2. click(selector) - Click an element by CSS selector
3. type(selector, text) - Type text into an input
4. scroll(direction) - Scroll up/down
5. wait(seconds) - Wait for N seconds
6. extract(selector) - Extract text from elements
7. screenshot() - Take a screenshot
8. done(answer) - Complete the task with answer

Respond with EXACTLY ONE line:
ACTION: action_name(argument)

For example:
ACTION: navigate(https://google.com)
ACTION: click(#search-button)
ACTION: type(input[name="q"], "hello world")
ACTION: scroll(down)
ACTION: wait(2)
ACTION: done(I found the answer: 42)
"""

class BrowserAgent:
    def __init__(self):
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None
        self.playwright = None
        self.history = []
        
    async def _init_browser(self):
        """Initialize stealth browser"""
        if self.playwright is None:
            self.playwright = await async_playwright().start()
        
        if self.browser is None:
            self.browser = await self.playwright.chromium.launch(
                args=STEALTH_ARGS,
                headless=True,
                ignore_default_args=["--enable-automation"],
            )
            
        if self.page is None:
            context = await self.browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
                locale="en-US",
                timezone_id="America/New_York",
                permissions=["geolocation"],
                extra_http_headers={
                    "Accept-Language": "en-US,en;q=0.9",
                },
            )
            self.page = await context.new_page()
            
            # Inject stealth scripts
            await self.page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
                Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
                window.chrome = { runtime: {} };
            """)
    
    async def _get_page_summary(self) -> str:
        """Get a summary of the current page"""
        try:
            # Get accessibility tree for better understanding
            tree = await self.page.accessibility.snapshot()
            if tree:
                return json.dumps(tree, indent=2)[:2000]
        except:
            pass
        return "Empty page"
    
    async def _call_ai(self, url: str, title: str, summary: str, task: str) -> str:
        """Call MiniMax AI to decide next action"""
        prompt = PROMPT_TEMPLATE.format(
            url=url,
            title=title or "No title",
            summary=summary,
            task=task
        )
        
        # Try MiniMax first, fallback to local
        try:
            from openai import OpenAI
            client = OpenAI(api_key=os.getenv("MINIMAX_API_KEY", "mock"), base_url="https://api.minimax.chat/v1")
            
            response = client.chat.completions.create(
                model="MiniMax-M2.5",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=500,
                temperature=0.7
            )
            return response.choices[0].message.content
        except Exception as e:
            # Fallback: simple rule-based
            return f"ACTION: done(Task completed with MiniMax error: {str(e)})"
    
    async def _parse_action(self, action_line: str) -> tuple[str, str]:
        """Parse AI action response"""
        action_line = action_line.strip()
        if not action_line.startswith("ACTION:"):
            return "done", f"Could not parse action: {action_line}"
        
        rest = action_line[7:].strip()
        if "(" in rest and rest.endswith(")"):
            name = rest[:rest.index("(")]
            arg = rest[rest.index("(")+1:-1]
            return name, arg
        return "done", rest
    
    async def execute(self, task: str, url: str, mode: str = "fast") -> dict:
        """Execute a browser task"""
        await self._init_browser()
        
        steps_executed = 0
        steps_failed = 0
        answer = None
        screenshot_b64 = None
        
        max_steps = 15 if mode == "fast" else 25
        
        # Navigate to start URL
        await self.page.goto(url, wait_until="domcontentloaded", timeout=30000)
        steps_executed += 1
        
        self.history.append({"step": steps_executed, "action": f"navigate({url})", "url": url})
        
        for _ in range(max_steps):
            # Get page state
            current_url = self.page.url
            title = await self.page.title()
            summary = await self._get_page_summary()
            
            # Call AI
            ai_response = await self._call_ai(current_url, title, summary, task)
            
            # Parse and execute
            action, arg = await self._parse_action(ai_response)
            
            try:
                if action == "navigate":
                    await self.page.goto(arg, wait_until="domcontentloaded", timeout=30000)
                    self.history.append({"step": steps_executed + 1, "action": f"navigate({arg})", "url": arg})
                    steps_executed += 1
                    
                elif action == "click":
                    await self.page.click(arg, timeout=5000)
                    self.history.append({"step": steps_executed + 1, "action": f"click({arg})", "url": current_url})
                    steps_executed += 1
                    
                elif action == "type":
                    parts = arg.split(",", 1)
                    if len(parts) == 2:
                        selector, text = parts
                        await self.page.fill(selector.strip(), text.strip())
                        await self.page.press(selector.strip(), "Enter")
                        self.history.append({"step": steps_executed + 1, "action": f"type({selector}, ...)", "url": current_url})
                        steps_executed += 1
                        
                elif action == "scroll":
                    if arg == "down":
                        await self.page.mouse.wheel(0, 500)
                    else:
                        await self.page.mouse.wheel(0, -500)
                    self.history.append({"step": steps_executed + 1, "action": f"scroll({arg})", "url": current_url})
                    steps_executed += 1
                    
                elif action == "wait":
                    await asyncio.sleep(float(arg))
                    steps_executed += 1
                    
                elif action == "extract":
                    text = await self.page.locator(arg).all_text_contents()
                    answer = "; ".join(text) if text else "No text found"
                    
                elif action == "done":
                    answer = arg
                    break
                    
            except Exception as e:
                steps_failed += 1
                if steps_failed > 3:
                    break
                continue
        
        # Final screenshot
        if self.page:
            screenshot_b64 = base64.b64encode(
                await self.page.screenshot(type="png")
            ).decode()
        
        return {
            "answer": answer or "Task completed without final answer",
            "steps_executed": steps_executed,
            "steps_failed": steps_failed,
            "screenshot": screenshot_b64,
            "history": self.history
        }
    
    async def stream_execute(self, task: str, url: str, mode: str) -> AsyncGenerator[dict, None]:
        """Stream step-by-step execution"""
        await self._init_browser()
        
        steps_executed = 0
        max_steps = 15 if mode == "fast" else 25
        
        # Initial navigate
        await self.page.goto(url, wait_until="domcontentloaded", timeout=30000)
        steps_executed += 1
        
        yield {"step": steps_executed, "action": "navigate", "url": url, "status": "executing"}
        
        for _ in range(max_steps):
            current_url = self.page.url
            title = await self.page.title()
            summary = await self._get_page_summary()
            
            ai_response = await self._call_ai(current_url, title, summary, task)
            action, arg = await self._parse_action(ai_response)
            
            yield {"step": steps_executed, "action": action, "argument": arg, "ai_reasoning": ai_response, "status": "executing"}
            
            try:
                if action == "navigate":
                    await self.page.goto(arg, wait_until="domcontentloaded", timeout=30000)
                    steps_executed += 1
                    
                elif action == "click":
                    await self.page.click(arg, timeout=5000)
                    steps_executed += 1
                    
                elif action == "type":
                    parts = arg.split(",", 1)
                    if len(parts) == 2:
                        await self.page.fill(parts[0].strip(), parts[1].strip())
                        await self.page.press(parts[0].strip(), "Enter")
                        steps_executed += 1
                        
                elif action == "scroll":
                    await self.page.mouse.wheel(0, 500 if arg == "down" else -500)
                    steps_executed += 1
                    
                elif action == "wait":
                    await asyncio.sleep(float(arg))
                    steps_executed += 1
                    
                elif action == "done":
                    yield {"step": steps_executed, "action": "done", "answer": arg, "status": "completed"}
                    break
                    
            except Exception as e:
                yield {"step": steps_executed, "action": "error", "error": str(e), "status": "retrying"}
                continue
            
            # Screenshot after each step
            if self.page:
                screenshot_b64 = base64.b64encode(
                    await self.page.screenshot(type="png")
                ).decode()
                yield {"step": steps_executed, "screenshot": screenshot_b64, "status": "snapshot"}
        
        await self.cleanup()
    
    async def cleanup(self):
        """Clean up resources"""
        if self.page:
            await self.page.close()
            self.page = None
        if self.browser:
            await self.browser.close()
            self.browser = None
        if self.playwright:
            await self.playwright.stop()
            self.playwright = None