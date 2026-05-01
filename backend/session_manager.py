"""
Named session persistence — cookies, localStorage, viewport, proxy, UA.
Inspired by Vessel's session system.
Sessions survive backend restarts.
"""
import json, os, asyncio, base64
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime

import re

SESSIONS_DIR = Path("~/.agent-browser/sessions").expanduser()
SESSIONS_DIR.mkdir(parents=True, exist_ok=True)

# Sanitize session name to prevent path traversal attacks
def _sanitize_session_name(name: str) -> str:
    """Strip anything that isn't alphanumeric, dash, underscore, or dot."""
    sanitized = re.sub(r"[^\w\-.]", "", name)
    if not sanitized or sanitized.startswith("."):
        sanitized = "_" + sanitized.lstrip(".")
    return sanitized


class SessionManager:
    def __init__(self, browser_agent):
        self.browser = browser_agent
        self.active_session_name: Optional[str] = None

    async def _get_local_storage(self) -> dict:
        """Retrieve all localStorage key-value pairs from the current page."""
        try:
            if self.browser.page and not self.browser.page.is_closed():
                local_storage = await self.browser.page.evaluate("""
                    () => {
                        const keys = Object.keys(localStorage);
                        const result = {};
                        for (const key of keys) {
                            try { result[key] = localStorage.getItem(key); } catch(_) {}
                        }
                        return result;
                    }
                """)
                return local_storage
        except Exception:
            pass
        return {}

    async def _apply_local_storage(self, local_storage: dict):
        """Apply localStorage key-value pairs to the current page."""
        try:
            if self.browser.page and not self.browser.page.is_closed():
                for key, value in local_storage.items():
                    await self.browser.page.evaluate(
                        "(k, v) => { try { localStorage.setItem(k, v); } catch(_) {} }",
                        key, value
                    )
        except Exception:
            pass

    async def save_session(self, name: str) -> dict:
        """Save current browser state as a named session."""
        cookies = []
        local_storage = {}
        try:
            if self.browser.context:
                cookies = await self.browser.context.cookies()
        except Exception:
            pass

        try:
            local_storage = await self._get_local_storage()
        except Exception:
            pass

        session_data = {
            "name": name,
            "saved_at": datetime.utcnow().isoformat(),
            "cookies": cookies,
            "local_storage": local_storage,
            "viewport": getattr(self.browser, "viewport", None),
            "user_agent": getattr(self.browser, "user_agent", None),
            "proxy": getattr(self.browser, "proxy_url", None),
        }

        safe_name = _sanitize_session_name(name)
        path = SESSIONS_DIR / f"{safe_name}.json"
        path.write_text(json.dumps(session_data, indent=2))
        os.chmod(path, 0o600)
        self.active_session_name = safe_name
        return {"saved": True, "name": safe_name, "path": str(path)}

    async def load_session(self, name: str) -> dict:
        """Restore browser state from a named session."""
        safe_name = _sanitize_session_name(name)
        path = SESSIONS_DIR / f"{safe_name}.json"
        if not path.exists():
            return {"error": f"Session '{safe_name}' not found"}

        session_data = json.loads(path.read_text())

        # Apply cookies
        try:
            if self.browser.context:
                await self.browser.context.clear_cookies()
                await self.browser.context.add_cookies(session_data.get("cookies", []))
        except Exception as e:
            return {"error": f"Failed to apply cookies: {e}"}

        # Apply local storage
        try:
            await self._apply_local_storage(session_data.get("local_storage", {}))
        except Exception as e:
            return {"error": f"Failed to apply localStorage: {e}"}

        self.active_session_name = safe_name
        return {"loaded": True, "name": safe_name}

    def list_sessions(self) -> list:
        """List all saved sessions (name, saved_at, url from cookies domain)."""
        sessions = []
        for p in SESSIONS_DIR.glob("*.json"):
            try:
                data = json.loads(p.read_text())
                # Try to extract URL from first cookie domain
                url = ""
                cookies = data.get("cookies", [])
                if cookies:
                    url = f"https://{cookies[0].get('domain', 'unknown')}"
                sessions.append({
                    "name": data.get("name", p.stem),
                    "saved_at": data.get("saved_at", ""),
                    "url": url,
                })
            except Exception:
                sessions.append({"name": p.stem, "saved_at": "", "url": ""})
        return sessions

    def delete_session(self, name: str) -> dict:
        """Delete a named session."""
        safe_name = _sanitize_session_name(name)
        path = SESSIONS_DIR / f"{safe_name}.json"
        if path.exists():
            path.unlink()
        return {"deleted": True, "name": safe_name}

    def get_session_path(self, name: str) -> str:
        """Return the file path for a named session."""
        safe_name = _sanitize_session_name(name)
        return str(SESSIONS_DIR / f"{safe_name}.json")
