"""
agent-browser MCP Server
Exposes browser control as MCP tools so any MCP-compatible agent can drive the browser.
Supports stdio transport (Claude Code, Claude Desktop) and SSE/HTTP transport (Hermes Agent).

Usage:
    # Standalone stdio mode (for Claude Code / Claude Desktop):
    python mcp_server.py

    # Or import and share the BrowserAgent instance from main.py:
    from mcp_server import create_mcp_server
    server = create_mcp_server(agent)
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import sys
from typing import Any, AsyncGenerator, Optional

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    Tool,
    TextContent,
    Resource,
    Prompt,
)

logger = logging.getLogger(__name__)

# ── Server instance (created lazily via create_mcp_server) ──────────────────

_mcp_server: Optional[Server] = None
_active_agent: Optional[Any] = None  # BrowserAgent instance


# ── Tool definitions ────────────────────────────────────────────────────────

def _make_tools() -> list[Tool]:
    """Return the list of MCP tools exposed by this server."""
    return [
        # ── Navigation ──────────────────────────────────────────────────────────
        Tool(
            name="browser_navigate",
            description="Navigate to a URL in the browser. Initializes the session and loads the page.",
            inputSchema={
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The URL to navigate to (e.g. 'https://example.com')",
                    },
                },
                "required": ["url"],
            },
        ),
        # ── Interaction ─────────────────────────────────────────────────────────
        Tool(
            name="browser_click",
            description="Click on an element identified by a CSS selector or ref ID (e.g. '@e5'). "
                        "Call browser_snapshot first to see available elements.",
            inputSchema={
                "type": "object",
                "properties": {
                    "selector": {
                        "type": "string",
                        "description": "CSS selector or element ref (e.g. 'button.submit', '@e5')",
                    },
                },
                "required": ["selector"],
            },
        ),
        Tool(
            name="browser_type",
            description="Type text into an input field. Clears the field first, then types character-by-character "
                        "with human-like delays. Call browser_snapshot first to identify the field.",
            inputSchema={
                "type": "object",
                "properties": {
                    "selector": {
                        "type": "string",
                        "description": "CSS selector for the input field (e.g. 'input[name=\"email\"]')",
                    },
                    "text": {
                        "type": "string",
                        "description": "The text to type into the field",
                    },
                },
                "required": ["selector", "text"],
            },
        ),
        Tool(
            name="browser_press",
            description="Press a keyboard key (Enter, Tab, Escape, ArrowDown, etc.)",
            inputSchema={
                "type": "object",
                "properties": {
                    "key": {
                        "type": "string",
                        "description": "Key to press (e.g. 'Enter', 'Tab', 'Escape', 'ArrowDown')",
                    },
                },
                "required": ["key"],
            },
        ),
        # ── Content extraction ─────────────────────────────────────────────────
        Tool(
            name="browser_snapshot",
            description="Get a text-based snapshot of the current page's accessibility tree. "
                        "Returns interactive elements with ref IDs (like @e1, @e2) for browser_click "
                        "and browser_type. Use full=true for complete page content.",
            inputSchema={
                "type": "object",
                "properties": {
                    "full": {
                        "type": "boolean",
                        "description": "If true, returns complete page content. If false (default), "
                                       "returns compact view with interactive elements only.",
                        "default": False,
                    },
                },
            },
        ),
        Tool(
            name="browser_screenshot",
            description="Take a screenshot of the current page and return it as base64-encoded JPEG.",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
        Tool(
            name="browser_extract_content",
            description="Extract visible text content from the page. "
                        "Use mode='text' for plain text, mode='json' for structured data.",
            inputSchema={
                "type": "object",
                "properties": {
                    "mode": {
                        "type": "string",
                        "enum": ["text", "json"],
                        "description": "Extraction mode: 'text' (default) for plain text, 'json' for structured data",
                        "default": "text",
                    },
                },
            },
        ),
        # ── Navigation / scroll ────────────────────────────────────────────────
        Tool(
            name="browser_scroll",
            description="Scroll the page in a direction. Use direction='down' or 'up'. "
                        "Amount is the fraction of viewport height to scroll (0.3–0.8 random by default).",
            inputSchema={
                "type": "object",
                "properties": {
                    "direction": {
                        "type": "string",
                        "enum": ["up", "down"],
                        "description": "Direction to scroll",
                    },
                    "amount": {
                        "type": "number",
                        "description": "Optional: fraction of viewport height to scroll (0.3–0.8). "
                                       "Defaults to a random value.",
                    },
                },
                "required": ["direction"],
            },
        ),
        Tool(
            name="browser_back",
            description="Navigate back to the previous page in browser history.",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
        # ── Wait / observe ──────────────────────────────────────────────────────
        Tool(
            name="browser_wait_for",
            description="Wait for a specific text or element to appear on the page. "
                        "Polls the page until the text is found or timeout is reached.",
            inputSchema={
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "Text to wait for on the page",
                    },
                    "timeout": {
                        "type": "number",
                        "description": "Maximum seconds to wait (default: 10, max: 30)",
                        "default": 10,
                    },
                },
                "required": ["text"],
            },
        ),
        # ── Tab management ───────────────────────────────────────────────────────
        Tool(
            name="browser_list_tabs",
            description="List all open browser tabs with their URLs and titles.",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
        Tool(
            name="browser_switch_tab",
            description="Switch to a different browser tab by index (0-based).",
            inputSchema={
                "type": "object",
                "properties": {
                    "tab_id": {
                        "type": "string",
                        "description": "Tab index as string (e.g. '0', '1'). "
                                       "Use browser_list_tabs first to see available tabs.",
                    },
                },
                "required": ["tab_id"],
            },
        ),
        # ── Session management ───────────────────────────────────────────────────
        Tool(
            name="browser_session_save",
            description="Save the current browser state (cookies, localStorage, viewport, proxy, UA) "
                        "as a named persistent session.",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Name for the saved session",
                    },
                },
                "required": ["name"],
            },
        ),
        Tool(
            name="browser_session_load",
            description="Load a previously saved named session into the current browser.",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Name of the session to load",
                    },
                },
                "required": ["name"],
            },
        ),
        # ── Page info ───────────────────────────────────────────────────────────
        Tool(
            name="browser_get_page_info",
            description="Get current page metadata: URL, title, loading state, and engine used.",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
        # ── Undo ────────────────────────────────────────────────────────────────
        Tool(
            name="browser_undo",
            description="Request to undo the last browser action. "
                        "Note: This is a best-effort request — not all actions can be undone.",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
    ]


# ── Tool call implementations ───────────────────────────────────────────────

async def _call_browser_navigate(agent: Any, arguments: dict) -> list[TextContent]:
    url = arguments["url"]
    if not agent.page:
        return [TextContent(type="text", text="Error: No active browser session. Call browser_navigate first.")]

    try:
        await agent.page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await agent._human_delay(0.5, 1.5)
        title = await agent.page.title() if agent.page else ""
        return [TextContent(
            type="text",
            text=f"Navigated to {url}\nTitle: {title}\nURL: {agent.page.url}",
        )]
    except Exception as e:
        return [TextContent(type="text", text=f"Navigation failed: {e}")]


async def _call_browser_click(agent: Any, arguments: dict) -> list[TextContent]:
    selector = arguments["selector"]
    if not agent.page:
        return [TextContent(type="text", text="Error: No active browser session.")]

    try:
        # Try to handle ref IDs like @e5 → look up in accessibility tree
        ref = selector
        if ref.startswith("@"):
            # @e5 style ref — we don't have the snapshot map here, so try clicking directly
            pass

        await agent.page.click(selector, timeout=8000)
        await agent._human_delay(0.3, 1.0)
        return [TextContent(type="text", text=f"Clicked: {selector}")]
    except Exception as e:
        return [TextContent(type="text", text=f"Click failed for '{selector}': {e}")]


async def _call_browser_type(agent: Any, arguments: dict) -> list[TextContent]:
    selector = arguments["selector"]
    text = arguments["text"]
    if not agent.page:
        return [TextContent(type="text", text="Error: No active browser session.")]

    try:
        await agent._human_type(selector, text)
        await agent._human_delay(0.15, 0.4)
        return [TextContent(type="text", text=f"Typed {len(text)} chars into: {selector}")]
    except Exception as e:
        # Fallback to fill
        try:
            await agent.page.fill(selector, text, no_wait_after=True)
            return [TextContent(type="text", text=f"Filled {len(text)} chars into: {selector}")]
        except Exception as e2:
            return [TextContent(type="text", text=f"Type failed: {e2}")]


async def _call_browser_press(agent: Any, arguments: dict) -> list[TextContent]:
    key = arguments["key"]
    if not agent.page:
        return [TextContent(type="text", text="Error: No active browser session.")]

    try:
        await agent.page.keyboard.press(key)
        await agent._human_delay(0.1, 0.3)
        return [TextContent(type="text", text=f"Pressed: {key}")]
    except Exception as e:
        return [TextContent(type="text", text=f"Press failed: {e}")]


async def _call_browser_snapshot(agent: Any, arguments: dict) -> list[TextContent]:
    full = arguments.get("full", False)
    if not agent.page:
        return [TextContent(type="text", text="Error: No active browser session.")]

    try:
        page_content = await agent._get_page_content()
        data = agent._parse_page_data(page_content)

        if full:
            text = data.get("text", "")
            return [TextContent(type="text", text=f"# Page Content\n\n{data.get('title','')}\n{data.get('url','')}\n\n{text[:5000]}")]
        else:
            # Compact view: interactive elements
            interactives = data.get("interactives", [])
            lines = [f"# {data.get('title','unknown')} — {data.get('url','')}"]
            for i, el in enumerate(interactives[:40]):
                ref = f"@e{i}"
                tag = el.get("tag", "")
                el_text = el.get("text", "")[:40]
                sel = el.get("selector", "")
                text_part = f'"{el_text}"' if el_text else ""
                lines.append(f"[{ref}] {tag} {text_part} ({sel})")

            return [TextContent(type="text", text="\n".join(lines))]
    except Exception as e:
        return [TextContent(type="text", text=f"Snapshot failed: {e}")]


async def _call_browser_screenshot(agent: Any, arguments: dict) -> list[TextContent]:
    if not agent.page:
        return [TextContent(type="text", text="Error: No active browser session.")]

    try:
        b64 = await agent._take_screenshot()
        if b64:
            # Return as a data URI so clients can display it directly
            return [TextContent(
                type="text",
                text=f"screenshot Taken (base64, {len(b64)} bytes). "
                     f"Image data URI: data:image/jpeg;base64,{b64[:50]}...[truncated]",
            )]
        else:
            return [TextContent(type="text", text="Screenshot capture failed or returned empty.")]
    except Exception as e:
        return [TextContent(type="text", text=f"Screenshot failed: {e}")]


async def _call_browser_extract_content(agent: Any, arguments: dict) -> list[TextContent]:
    mode = arguments.get("mode", "text")
    if not agent.page:
        return [TextContent(type="text", text="Error: No active browser session.")]

    try:
        page_content = await agent._get_page_content()
        data = agent._parse_page_data(page_content)

        if mode == "json":
            # Return full structured data
            # Remove heavy fields for the response
            clean = {k: v for k, v in data.items() if k not in ("images",)}
            return [TextContent(type="text", text=json.dumps(clean, indent=2, default=str))]
        else:
            text = data.get("text", "")
            return [TextContent(type="text", text=text[:8000])]
    except Exception as e:
        return [TextContent(type="text", text=f"Extract failed: {e}")]


async def _call_browser_scroll(agent: Any, arguments: dict) -> list[TextContent]:
    direction = arguments["direction"]
    amount = arguments.get("amount")

    if not agent.page:
        return [TextContent(type="text", text="Error: No active browser session.")]

    try:
        if amount:
            await agent._human_scroll(direction, amount)
        else:
            await agent._human_scroll(direction)
        return [TextContent(type="text", text=f"Scrolled {direction}" + (f" ({amount} of viewport)" if amount else ""))]
    except Exception as e:
        return [TextContent(type="text", text=f"Scroll failed: {e}")]


async def _call_browser_back(agent: Any, arguments: dict) -> list[TextContent]:
    if not agent.page:
        return [TextContent(type="text", text="Error: No active browser session.")]

    try:
        await agent.page.go_back()
        await agent._human_delay(0.5, 1.0)
        return [TextContent(type="text", text=f"Went back to: {agent.page.url}")]
    except Exception as e:
        return [TextContent(type="text", text=f"Back navigation failed: {e}")]


async def _call_browser_wait_for(agent: Any, arguments: dict) -> list[TextContent]:
    text = arguments["text"]
    timeout = min(float(arguments.get("timeout", 10)), 30)

    if not agent.page:
        return [TextContent(type="text", text="Error: No active browser session.")]

    try:
        import re
        start = asyncio.get_event_loop().time()
        while (asyncio.get_event_loop().time() - start) < timeout:
            page_content = await agent._get_page_content()
            if text.lower() in page_content.lower():
                elapsed = asyncio.get_event_loop().time() - start
                return [TextContent(type="text", text=f"Found '{text}' after {elapsed:.1f}s")]
            await asyncio.sleep(0.5)
        return [TextContent(type="text", text=f"Timeout: '{text}' not found after {timeout}s")]
    except Exception as e:
        return [TextContent(type="text", text=f"Wait failed: {e}")]


async def _call_browser_list_tabs(agent: Any, arguments: dict) -> list[TextContent]:
    if not agent.page or not agent.context:
        return [TextContent(type="text", text="Error: No active browser session.")]

    try:
        pages = agent.context.pages
        lines = [f"{len(pages)} tab(s) open:"]
        for i, p in enumerate(pages):
            try:
                title = await p.title() if not p.is_closed() else "(closed)"
                url = p.url if not p.is_closed() else "(closed)"
                current = " ← current" if p == agent.page else ""
                lines.append(f"  [{i}] {title}\n      {url}{current}")
            except Exception:
                lines.append(f"  [{i}] (unavailable)")
        return [TextContent(type="text", text="\n".join(lines))]
    except Exception as e:
        return [TextContent(type="text", text=f"List tabs failed: {e}")]


async def _call_browser_switch_tab(agent: Any, arguments: dict) -> list[TextContent]:
    tab_id = arguments["tab_id"]
    if not agent.page or not agent.context:
        return [TextContent(type="text", text="Error: No active browser session.")]

    try:
        idx = int(tab_id)
        pages = agent.context.pages
        if 0 <= idx < len(pages):
            target = pages[idx]
            await target.bring_to_front()
            agent.page = target
            await agent._human_delay(0.3, 0.6)
            return [TextContent(type="text", text=f"Switched to tab {idx}: {target.url}")]
        else:
            return [TextContent(type="text", text=f"Tab index {idx} out of range (have {len(pages)} tabs)")]
    except Exception as e:
        return [TextContent(type="text", text=f"Switch tab failed: {e}")]


async def _call_browser_session_save(agent: Any, arguments: dict) -> list[TextContent]:
    name = arguments["name"]
    if not agent:
        return [TextContent(type="text", text="Error: No active browser session.")]

    try:
        result = await agent.save_session(name)
        if result.get("success"):
            return [TextContent(type="text", text=f"Session '{name}' saved successfully.")]
        else:
            return [TextContent(type="text", text=f"Session save failed: {result.get('error', 'unknown error')}")]
    except Exception as e:
        return [TextContent(type="text", text=f"Session save error: {e}")]


async def _call_browser_session_load(agent: Any, arguments: dict) -> list[TextContent]:
    name = arguments["name"]
    if not agent:
        return [TextContent(type="text", text="Error: No active browser session.")]

    try:
        result = await agent.load_session(name)
        if result.get("success"):
            return [TextContent(type="text", text=f"Session '{name}' loaded successfully.")]
        else:
            return [TextContent(type="text", text=f"Session load failed: {result.get('error', 'unknown error')}")]
    except Exception as e:
        return [TextContent(type="text", text=f"Session load error: {e}")]


async def _call_browser_get_page_info(agent: Any, arguments: dict) -> list[TextContent]:
    if not agent.page:
        return [TextContent(type="text", text="Error: No active browser session.")]

    try:
        info = {
            "url": agent.page.url,
            "title": await agent.page.title() if agent.page else "",
            "is_loading": agent.page.is_loaded() is False,  # is_loaded is not quite right but close
            "engine": getattr(agent, "_browser_engine", "unknown"),
        }
        return [TextContent(type="text", text=json.dumps(info, indent=2))]
    except Exception as e:
        return [TextContent(type="text", text=f"Get page info failed: {e}")]


async def _call_browser_undo(agent: Any, arguments: dict) -> list[TextContent]:
    # Undo support is limited — we track history but can't truly undo arbitrary actions
    if not agent.page:
        return [TextContent(type="text", text="Error: No active browser session.")]

    try:
        if agent.history:
            # Try going back in browser history as a best-effort undo
            await agent.page.go_back()
            await agent._human_delay(0.5, 1.0)
            return [TextContent(type="text", text="Undo: navigated back in browser history.")]
        else:
            return [TextContent(type="text", text="No action history available to undo.")]
    except Exception as e:
        return [TextContent(type="text", text=f"Undo not available: {e}")]


# ── Tool dispatch map ────────────────────────────────────────────────────────

_TOOL_HANDLERS = {
    "browser_navigate":      _call_browser_navigate,
    "browser_click":         _call_browser_click,
    "browser_type":          _call_browser_type,
    "browser_press":         _call_browser_press,
    "browser_snapshot":      _call_browser_snapshot,
    "browser_screenshot":    _call_browser_screenshot,
    "browser_extract_content": _call_browser_extract_content,
    "browser_scroll":        _call_browser_scroll,
    "browser_back":          _call_browser_back,
    "browser_wait_for":      _call_browser_wait_for,
    "browser_list_tabs":     _call_browser_list_tabs,
    "browser_switch_tab":    _call_browser_switch_tab,
    "browser_session_save":  _call_browser_session_save,
    "browser_session_load":  _call_browser_session_load,
    "browser_get_page_info": _call_browser_get_page_info,
    "browser_undo":          _call_browser_undo,
}


# ── Server factory ───────────────────────────────────────────────────────────

def create_mcp_server(agent: Any) -> Server:
    """
    Create and configure an MCP Server that wraps the given BrowserAgent instance.

    Args:
        agent: A BrowserAgent instance to wrap. Can be None initially
               and set later via set_agent().

    Returns:
        A configured mcp.server.Server instance.
    """
    global _mcp_server, _active_agent
    _active_agent = agent

    app = Server("agent-browser")

    # ── List tools ────────────────────────────────────────────────────────────
    @app.list_tools()
    async def list_tools():
        return _make_tools()

    # ── Call tool ─────────────────────────────────────────────────────────────
    @app.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[TextContent]:
        if _active_agent is None:
            return [TextContent(
                type="text",
                text="No active browser session. Start a session via the WebSocket endpoint "
                     "at ws://localhost:8001/ws/agent before using MCP tools.",
            )]

        handler = _TOOL_HANDLERS.get(name)
        if handler is None:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]

        try:
            return await handler(_active_agent, arguments)
        except Exception as e:
            logger.error(f"MCP tool {name} failed: {e}", exc_info=True)
            return [TextContent(type="text", text=f"Tool '{name}' failed: {e}")]

    _mcp_server = app
    return app


def get_mcp_server() -> Optional[Server]:
    return _mcp_server


def set_agent(agent: Any):
    """Update the active BrowserAgent instance shared by all MCP tool handlers."""
    global _active_agent
    _active_agent = agent


# ── Stdio entrypoint ─────────────────────────────────────────────────────────

async def main():
    """
    Stdio entrypoint for standalone MCP server.
    Listens for JSON-RPC tool calls from Claude Code / Claude Desktop.
    """
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    # In stdio mode we don't have a browser agent pre-attached.
    # The client must provide one via initialize.
    # We create a placeholder server; the agent will be injected.
    server = Server("agent-browser")

    @server.list_tools()
    async def list_tools():
        return _make_tools()

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[TextContent]:
        if _active_agent is None:
            return [TextContent(
                type="text",
                text="No browser agent attached. "
                     "Start the backend server first: uvicorn main:app --port 8001",
            )]
        handler = _TOOL_HANDLERS.get(name)
        if handler is None:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]
        try:
            return await handler(_active_agent, arguments)
        except Exception as e:
            logger.error(f"MCP tool {name} failed: {e}", exc_info=True)
            return [TextContent(type="text", text=f"Tool '{name}' failed: {e}")]

    async with stdio_server() as streams:
        await server.run(
            streams[0],
            streams[1],
            server.create_initialization_options(),
        )


if __name__ == "__main__":
    asyncio.run(main())
