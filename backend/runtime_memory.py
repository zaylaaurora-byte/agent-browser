"""Runtime memory store for cross-workflow browser automation.

Persists reusable state across sessions/domains/workflow types so the agent
can resume and improve repeat tasks (jobs, signup, checkout, social actions).
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


DEFAULT_DB = Path.home() / ".agent-browser" / "runtime_memory.db"


@dataclass
class MemoryProfile:
    domain: str
    workflow: str
    payload: dict[str, Any]
    updated_at: str


class RuntimeMemory:
    def __init__(self, db_path: Optional[Path] = None) -> None:
        self.db_path = Path(db_path) if db_path else DEFAULT_DB
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS runtime_profiles (
                    domain TEXT NOT NULL,
                    workflow TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (domain, workflow)
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_runtime_profiles_updated
                ON runtime_profiles(updated_at DESC)
                """
            )

    def upsert_profile(self, domain: str, workflow: str, payload: dict[str, Any]) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO runtime_profiles(domain, workflow, payload, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(domain, workflow)
                DO UPDATE SET payload=excluded.payload, updated_at=excluded.updated_at
                """,
                (domain.strip().lower(), workflow.strip().lower(), json.dumps(payload), now),
            )

    def get_profile(self, domain: str, workflow: str) -> Optional[MemoryProfile]:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT domain, workflow, payload, updated_at
                FROM runtime_profiles
                WHERE domain = ? AND workflow = ?
                """,
                (domain.strip().lower(), workflow.strip().lower()),
            ).fetchone()
        if not row:
            return None
        return MemoryProfile(
            domain=row["domain"],
            workflow=row["workflow"],
            payload=json.loads(row["payload"]),
            updated_at=row["updated_at"],
        )

    def list_profiles(self, limit: int = 50) -> list[MemoryProfile]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT domain, workflow, payload, updated_at
                FROM runtime_profiles
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        out: list[MemoryProfile] = []
        for row in rows:
            out.append(
                MemoryProfile(
                    domain=row["domain"],
                    workflow=row["workflow"],
                    payload=json.loads(row["payload"]),
                    updated_at=row["updated_at"],
                )
            )
        return out

    def delete_profile(self, domain: str, workflow: str) -> int:
        with self._connect() as conn:
            cur = conn.execute(
                "DELETE FROM runtime_profiles WHERE domain = ? AND workflow = ?",
                (domain.strip().lower(), workflow.strip().lower()),
            )
            return cur.rowcount
