"""Browser Agent - AI-controlled browser automation with stealth"""
import asyncio
import os
import json
import base64
import random
import logging
from typing import AsyncGenerator, Optional
from datetime import datetime

from playwright.async_api import async_playwright, Browser, Page, BrowserContext

logger = logging.getLogger(__name__)

# Stealth browser arguments
STEALTH_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--disable-dev-shm-usage",
    "--no-sandbox",
    "--disable-setuid-sandbox",
    "--disable-web-security",
    "--window-size=1920,1080",
    "--start-maximized",
    "--disable-infobars",
    "--disable-background-timer-throttling",
    "--disable-backgrounding-occluded-windows",
    "--disable-renderer-backgrounding",
]

# Realistic user agents (rotate)
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
]

STEALTH_JS = """
    // Remove webdriver flag
    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
    
    // Fake plugins
    Object.defineProperty(navigator, 'plugins', {
        get: () => {
            const plugins = [
                { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer' },
                { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai' },
                { name: 'Native Client', filename: 'internal-nacl-plugin' },
            ];
            plugins.length = 3;
            return plugins;
        }
    });
    
    // Fake languages
    Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
    
    // Fake Chrome runtime
    window.chrome = { runtime: {}, loadTimes: function(){}, csi: function(){} };
    
    // Fake permissions
    const originalQuery = window.navigator.permissions.query;
    window.navigator.permissions.query = (parameters) =>
        parameters.name === 'notifications'
            ? Promise.resolve({ state: Notification.permission })
            : originalQuery(parameters);
    
    // Fake WebGL vendor
    const getParameter = WebGLRenderingContext.prototype.getParameter;
    WebGLRenderingContext.prototype.getParameter = function(parameter) {
        if (parameter === 37445) return 'Intel Inc.';
        if (parameter === 37446) return 'Intel Iris OpenGL Engine';
        return getParameter.call(this, parameter);
    };
    
    // Remove automation indicators
    delete window.cdc_adoQpoasnfa76pfcZLmcfl_Array;
    delete window.cdc_adoQpoasnfa76pfcZLmcfl_Promise;
    delete window.cdc_adoQpoasnfa76pfcZLmcfl_Symbol;
"""

SYSTEM_PROMPT = """You are a browser automation agent. You control a web browser to complete tasks.

RULES:
- Respond with EXACTLY ONE action per message
- Use the ACTION format exactly as shown
- Be precise with CSS selectors
- If unsure, take a screenshot first to see the page

Available actions:
- ACTION: navigate(url)
- ACTION: click(selector)  
- ACTION: type(selector, text)
- ACTION: scroll(direction) — "up" or "down"
- ACTION: wait(seconds)
- ACTION: screenshot()
- ACTION: done(answer) — complete the task with your answer

Examples:
ACTION: navigate(https://google.com)
ACTION: click(#search-button)
ACTION: type(input[name="q"], "hello world")
ACTION: scroll(down)
ACTION: wait(2)
ACTION: done(The page title is "Example Domain")
"""


class BrowserAgent:
    def __init__(self):
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.history: list = []

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

        if self.context is None:
            ua = random.choice(USER_AGENTS)
            self.context = await self.browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent=ua,
                locale="en-US",
                timezone_id="America/New_York",
                extra_http_headers={
                    "Accept-Language": "en-US,en;q=0.9",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                    "Accept-Encoding": "gzip, deflate, br",
                    "Connection": "keep-alive",
                    "Upgrade-Insecure-Requests": "1",
                    "Sec-Fetch-Dest": "document",
                    "Sec-Fetch-Mode": "navigate",
                    "Sec-Fetch-Site": "none",
                    "Sec-Fetch-User": "?1",
                    "Cache-Control": "max-age=0",
                },
                screen={"width": 1920, "height": 1080},
                color_scheme="dark",
            )
            self.page = await self.context.new_page()

            # Inject stealth scripts before every page load
            await self.page.add_init_script(STEALTH_JS)

            # Default timeout
            self.page.set_default_timeout(15000)
            self.page.set_default_navigation_timeout(30000)

    async def _human_delay(self, min_s: float = 0.5, max_s: float = 2.0):
        """Random human-like delay"""
        await asyncio.sleep(random.uniform(min_s, max_s))

    async def _get_page_content(self) -> str:
        """Get readable page content for AI"""
        try:
            content = await self.page.evaluate("""() => {
                const body = document.body;
                if (!body) return 'Empty page';
                
                // Get all visible text
                const walker = document.createTreeWalker(body, NodeFilter.SHOW_TEXT, {
                    acceptNode: (node) => {
                        const style = window.getComputedStyle(node.parentElement);
                        return style.display !== 'none' && style.visibility !== 'hidden' 
                            ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT;
                    }
                });
                
                const texts = [];
                while (walker.nextNode()) {
                    const t = walker.currentNode.textContent.trim();
                    if (t) texts.push(t);
                }
                
                // Get interactive elements
                const interactives = [];
                document.querySelectorAll('a, button, input, select, textarea, [role="button"], [onclick]').forEach(el => {
                    const tag = el.tagName.toLowerCase();
                    const text = el.textContent?.trim()?.slice(0, 50) || '';
                    const href = el.getAttribute('href') || '';
                    const type = el.getAttribute('type') || '';
                    const name = el.getAttribute('name') || '';
                    const id = el.getAttribute('id') || '';
                    const cls = el.getAttribute('class') || '';
                    const placeholder = el.getAttribute('placeholder') || '';
                    
                    let selector = '';
                    if (id) selector = `#${id}`;
                    else if (name) selector = `${tag}[name="${name}"]`;
                    else if (cls) selector = `${tag}.${cls.split(' ')[0]}`;
                    else selector = tag;
                    
                    interactives.push({
                        selector,
                        tag,
                        text: text.slice(0, 30),
                        href: href.slice(0, 50),
                        type,
                        placeholder: placeholder.slice(0, 30)
                    });
                });
                
                return JSON.stringify({
                    url: window.location.href,
                    title: document.title,
                    text: texts.slice(0, 100).join(' ').slice(0, 2000),
                    interactives: interactives.slice(0, 30)
                });
            }""")
            return content
        except Exception as e:
            return json.dumps({"error": str(e), "url": str(self.page.url if self.page else "none")})

    async def _call_ai(self, task: str, page_content: str) -> str:
        """Call AI model to decide next action"""
        try:
            from openai import OpenAI

            api_key = os.getenv("MINIMAX_API_KEY") or os.getenv("OPENAI_API_KEY")
            base_url = os.getenv("MINIMAX_BASE_URL", "https://api.minimax.chat/v1")
            model = os.getenv("AI_MODEL", "MiniMax-M2.5")

            if not api_key:
                # Fallback: simple heuristic-based action
                return self._fallback_ai(task, page_content)

            client = OpenAI(api_key=api_key, base_url=base_url)

            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": f"Task: {task}\n\nCurrent page state:\n{page_content}"}
                ],
                max_tokens=300,
                temperature=0.3,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.warning(f"AI call failed: {e}")
            return self._fallback_ai(task, page_content)

    def _fallback_ai(self, task: str, page_content: str) -> str:
        """Rule-based fallback when AI is unavailable"""
        try:
            data = json.loads(page_content) if page_content.startswith("{") else {}
            title = data.get("title", "")
            text = data.get("text", "")
            
            task_lower = task.lower()
            
            # Simple task matching
            if "title" in task_lower or "what" in task_lower:
                return f'ACTION: done(The page title is "{title}". Text on page: {text[:200]})'
            if "text" in task_lower or "content" in task_lower or "visible" in task_lower:
                return f'ACTION: done(Visible text: {text[:500]})'
            if "screenshot" in task_lower:
                return "ACTION: screenshot()"
            if "click" in task_lower:
                interactives = data.get("interactives", [])
                if interactives:
                    target = interactives[0]
                    return f'ACTION: click({target["selector"]})'
                return f'ACTION: done(No clickable elements found. Page title: {title})'
            
            return f'ACTION: done(Page title: "{title}". Content: {text[:300]})'
        except:
            return f'ACTION: done(Could not parse page. Task was: {task})'

    def _parse_action(self, response: str) -> tuple:
        """Parse AI response into (action, argument)"""
        response = response.strip()
        
        # Find ACTION: line
        for line in response.split("\n"):
            line = line.strip()
            if line.startswith("ACTION:"):
                rest = line[7:].strip()
                if "(" in rest and rest.endswith(")"):
                    name = rest[:rest.index("(")].strip()
                    arg = rest[rest.index("(")+1:-1].strip()
                    return name, arg
                return "done", rest
        
        # No ACTION found — treat as done
        return "done", response[:200]

    async def _execute_action(self, action: str, arg: str) -> dict:
        """Execute a single browser action"""
        result = {"action": action, "arg": arg, "success": False, "error": None}
        
        try:
            if action == "navigate":
                url = arg if arg.startswith("http") else f"https://{arg}"
                await self.page.goto(url, wait_until="domcontentloaded", timeout=30000)
                await self._human_delay(0.5, 1.5)
                result["success"] = True
                result["url"] = self.page.url

            elif action == "click":
                await self.page.click(arg, timeout=5000)
                await self._human_delay(0.3, 1.0)
                result["success"] = True

            elif action == "type":
                parts = arg.split(",", 1)
                if len(parts) == 2:
                    selector, text = parts[0].strip(), parts[1].strip()
                    await self.page.click(selector)
                    await self._human_delay(0.1, 0.3)
                    # Type with random delays between keystrokes
                    for char in text:
                        await self.page.keyboard.type(char, delay=random.randint(30, 120))
                    result["success"] = True
                else:
                    result["error"] = "Invalid type format: use selector, text"

            elif action == "scroll":
                amount = random.randint(300, 700)
                direction = amount if arg == "down" else -amount
                await self.page.mouse.wheel(0, direction)
                await self._human_delay(0.3, 0.8)
                result["success"] = True

            elif action == "wait":
                seconds = min(float(arg), 10)
                await asyncio.sleep(seconds)
                result["success"] = True

            elif action == "screenshot":
                result["success"] = True
                result["screenshot"] = True  # Flag to take screenshot

            elif action == "done":
                result["success"] = True
                result["answer"] = arg

        except Exception as e:
            result["error"] = str(e)[:200]
        
        return result

    async def _take_screenshot(self) -> str:
        """Take screenshot and return base64"""
        if self.page:
            ss = await self.page.screenshot(type="png", full_page=False)
            return base64.b64encode(ss).decode()
        return ""

    async def execute(self, task: str, url: str, mode: str = "fast") -> dict:
        """Execute a browser task — returns full result"""
        await self._init_browser()

        steps_executed = 0
        steps_failed = 0
        answer = None
        max_steps = 15 if mode == "fast" else 25

        # Navigate to start URL
        try:
            await self.page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await self._human_delay(1.0, 2.0)
            steps_executed += 1
            self.history.append({"step": 1, "action": f"navigate({url})", "status": "ok"})
        except Exception as e:
            return {
                "answer": f"Failed to navigate to {url}: {str(e)}",
                "steps_executed": 0,
                "steps_failed": 1,
                "screenshot": await self._take_screenshot(),
                "history": self.history,
            }

        for step_num in range(2, max_steps + 1):
            # Get page state
            page_content = await self._get_page_content()

            # Call AI
            ai_response = await self._call_ai(task, page_content)
            action, arg = self._parse_action(ai_response)

            self.history.append({
                "step": step_num,
                "action": action,
                "arg": arg[:100] if arg else "",
                "ai_response": ai_response[:200],
            })

            # Execute
            result = await self._execute_action(action, arg)

            if result["success"]:
                steps_executed += 1
                
                if action == "done":
                    answer = result.get("answer", arg)
                    break
                elif result.get("screenshot"):
                    # Just a screenshot action, continue
                    pass
            else:
                steps_failed += 1
                if steps_failed > 3:
                    answer = f"Stopped after {steps_failed} consecutive failures"
                    break

        # Final screenshot
        screenshot = await self._take_screenshot()
        await self.cleanup()

        return {
            "answer": answer or "Task completed",
            "steps_executed": steps_executed,
            "steps_failed": steps_failed,
            "screenshot": screenshot,
            "history": self.history,
        }

    async def stream_execute(self, task: str, url: str, mode: str) -> AsyncGenerator[dict, None]:
        """Stream step-by-step execution via WebSocket"""
        await self._init_browser()

        steps_executed = 0
        max_steps = 15 if mode == "fast" else 25

        # Navigate to start
        try:
            await self.page.goto(url, wait_until="domcontentloaded", timeout=30000)
            steps_executed += 1
            yield {"step": steps_executed, "action": "navigate", "arg": url, "status": "executing"}
        except Exception as e:
            yield {"step": 0, "action": "error", "error": f"Navigation failed: {str(e)}", "status": "failed"}
            return

        for step_num in range(2, max_steps + 1):
            # Get page state
            page_content = await self._get_page_content()

            # Call AI
            ai_response = await self._call_ai(task, page_content)
            action, arg = self._parse_action(ai_response)

            # Send AI reasoning
            yield {
                "step": step_num,
                "action": action,
                "argument": arg[:100] if arg else "",
                "ai_reasoning": ai_response[:300],
                "status": "thinking",
            }

            # Execute
            result = await self._execute_action(action, arg)

            if result["success"]:
                steps_executed += 1
                
                if action == "done":
                    yield {
                        "step": step_num,
                        "action": "done",
                        "answer": result.get("answer", arg),
                        "status": "completed",
                        "screenshot": await self._take_screenshot(),
                    }
                    return
            else:
                yield {
                    "step": step_num,
                    "action": "error",
                    "error": result.get("error", "Unknown error"),
                    "status": "retrying",
                }
                continue

            # Send screenshot after each action
            screenshot = await self._take_screenshot()
            yield {
                "step": step_num,
                "action": action,
                "screenshot": screenshot,
                "url": self.page.url if self.page else "",
                "status": "snapshot",
            }

            # Human-like delay between steps
            await self._human_delay(0.5, 1.5)

        # Max steps reached
        yield {
            "step": steps_executed,
            "action": "done",
            "answer": f"Reached maximum steps ({max_steps})",
            "status": "completed",
            "screenshot": await self._take_screenshot(),
        }

    async def cleanup(self):
        """Clean up all resources"""
        try:
            if self.page and not self.page.is_closed():
                await self.page.close()
        except:
            pass
        self.page = None
        
        try:
            if self.context:
                await self.context.close()
        except:
            pass
        self.context = None
        
        try:
            if self.browser:
                await self.browser.close()
        except:
            pass
        self.browser = None
        
        try:
            if self.playwright:
                await self.playwright.stop()
        except:
            pass
        self.playwright = None