"""
Action History + Undo System — inspired by Vessel's AgentRuntime.
Captures state snapshots before undoable actions.
Restores browser to previous state on undo.
"""
import json
import asyncio
from datetime import datetime
from typing import Optional, List
from dataclasses import dataclass, asdict
from enum import Enum


class ActionStatus(Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    UNDONE = "undone"


@dataclass
class ActionEntry:
    id: str
    name: str
    args: dict
    timestamp: str
    status: str
    result: str
    tab_id: Optional[str] = None


@dataclass
class UndoSnapshot:
    id: str
    action_name: str
    captured_at: str
    url: str
    title: str
    cookies: list
    scroll_position: dict
    local_storage: dict


class ActionHistory:
    MAX_HISTORY = 120
    MAX_SNAPSHOTS = 10
    UNDOABLE_ACTIONS = {
        "navigate", "click", "type", "type_text", "submit_form",
        "scroll", "hover", "dblclick", "select_option",
        "fill", "check", "press_key",
    }

    def __init__(self, browser_agent):
        self.browser = browser_agent
        self.actions: List[ActionEntry] = []
        self.snapshots: List[UndoSnapshot] = []
        self._counter = 0

    def _next_id(self) -> str:
        self._counter += 1
        return f"action_{self._counter}_{int(datetime.utcnow().timestamp())}"

    def is_undoable(self, action_name: str) -> bool:
        return action_name in self.UNDOABLE_ACTIONS

    async def capture_snapshot(self, action_name: str) -> UndoSnapshot:
        """Capture browser state before an undoable action."""
        context = self.browser.context
        page = self.browser.page

        # Capture URL + title
        url = page.url
        title = await page.title()

        # Capture cookies
        cookies = await context.cookies()

        # Capture scroll position
        scroll_pos = await page.evaluate("""
            ({ x: window.scrollX, y: window.scrollY })
        """)

        # Capture localStorage
        local_storage = await page.evaluate("""
            Object.fromEntries(Object.keys(localStorage).map(k => [k, localStorage.getItem(k)]))
        """)

        snapshot = UndoSnapshot(
            id=self._next_id(),
            action_name=action_name,
            captured_at=datetime.utcnow().isoformat(),
            url=url,
            title=title,
            cookies=cookies,
            scroll_position=scroll_pos,
            local_storage=local_storage,
        )

        self.snapshots.append(snapshot)
        # Keep only last MAX_SNAPSHOTS
        if len(self.snapshots) > self.MAX_SNAPSHOTS:
            self.snapshots = self.snapshots[-self.MAX_SNAPSHOTS:]

        return snapshot

    async def undo_last(self) -> dict:
        """Restore browser to the state before the last undoable action."""
        if not self.snapshots:
            return {"error": "No actions to undo"}

        snapshot = self.snapshots.pop()

        # Record as undone
        if self.actions:
            last = self.actions[-1]
            last.status = ActionStatus.UNDONE.value

        # Restore cookies
        context = self.browser.context
        await context.clear_cookies()
        if snapshot.cookies:
            await context.add_cookies(snapshot.cookies)

        # Restore localStorage — use params to avoid JS injection
        page = self.browser.page
        if snapshot.local_storage:
            for k, v in snapshot.local_storage.items():
                try:
                    await page.evaluate(
                        "(k, v) => { try { localStorage.setItem(k, v); } catch(_) {} }",
                        k, v
                    )
                except Exception:
                    pass

        # Navigate back to the URL
        if snapshot.url != page.url:
            await page.goto(snapshot.url, wait_until="domcontentloaded")

        # Restore scroll position — guard with numeric coercion
        if snapshot.scroll_position:
            x = float(snapshot.scroll_position.get('x', 0) or 0)
            y = float(snapshot.scroll_position.get('y', 0) or 0)
            await page.evaluate(
                "(x, y) => window.scrollTo(x, y)",
                x, y
            )

        return {
            "undone": True,
            "action": snapshot.action_name,
            "restored_url": snapshot.url,
        }

    def record_action(
        self,
        name: str,
        args: dict,
        status: str,
        result: str,
        tab_id: Optional[str] = None,
    ):
        entry = ActionEntry(
            id=self._next_id(),
            name=name,
            args=args,
            timestamp=datetime.utcnow().isoformat(),
            status=status,
            result=result,
            tab_id=tab_id,
        )
        self.actions.append(entry)
        if len(self.actions) > self.MAX_HISTORY:
            self.actions = self.actions[-self.MAX_HISTORY:]
        return entry

    def get_history(self, limit: int = 50) -> List[dict]:
        return [asdict(a) for a in self.actions[-limit:]]

    def get_last_snapshot(self) -> Optional[dict]:
        if not self.snapshots:
            return None
        return asdict(self.snapshots[-1])
