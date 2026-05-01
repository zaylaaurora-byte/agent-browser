"""
run_db.py — SQLite Run History for Agent Browser

Schema:
  runs(id, session_id, created_at, task, url, mode, status,
       final_answer, steps_count, failed_count, duration_ms, error)
  steps(id, run_id, step_num, action, argument, status, screenshot_path,
        ai_reasoning, observation, duration_ms, model_name)
"""
import sqlite3
import json
import threading
from pathlib import Path
from datetime import datetime
from typing import Optional

RUNS_DB = Path("~/.agent-browser/runs.db").expanduser()
SCREENSHOTS_DIR = Path("~/.agent-browser/screenshots").expanduser()

RUNS_DB.parent.mkdir(parents=True, exist_ok=True)
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)

_local = threading.local()


def _get_conn() -> sqlite3.Connection:
    if not hasattr(_local, "conn"):
        _local.conn = sqlite3.connect(str(RUNS_DB), check_same_thread=False)
        _local.conn.row_factory = sqlite3.Row
    return _local.conn


def init_db():
    """Create tables if they don't exist."""
    conn = _get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS runs (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id      TEXT    NOT NULL UNIQUE,
            created_at      TEXT    NOT NULL,
            task            TEXT,
            url             TEXT,
            mode            TEXT    DEFAULT 'fast',
            status          TEXT    DEFAULT 'running',
            final_answer    TEXT,
            steps_count     INTEGER DEFAULT 0,
            failed_count    INTEGER DEFAULT 0,
            duration_ms     INTEGER,
            error           TEXT
        );
        CREATE TABLE IF NOT EXISTS steps (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id          INTEGER NOT NULL,
            step_num        INTEGER NOT NULL,
            action          TEXT,
            argument        TEXT,
            status          TEXT,
            screenshot_path TEXT,
            ai_reasoning   TEXT,
            observation     TEXT,
            duration_ms     INTEGER,
            model_name      TEXT,
            FOREIGN KEY (run_id) REFERENCES runs(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_runs_session   ON runs(session_id);
        CREATE INDEX IF NOT EXISTS idx_runs_created   ON runs(created_at);
        CREATE INDEX IF NOT EXISTS idx_steps_run_id   ON steps(run_id, step_num);
    """)
    conn.commit()


def create_run(session_id: str, task: str, url: str, mode: str) -> int:
    conn = _get_conn()
    now = datetime.utcnow().isoformat()
    cursor = conn.execute(
        """INSERT INTO runs (session_id, created_at, task, url, mode, status)
           VALUES (?, ?, ?, ?, ?, 'running')""",
        (session_id, now, task, url, mode),
    )
    conn.commit()
    return cursor.lastrowid


def update_run(
    run_id: int,
    status: Optional[str] = None,
    final_answer: Optional[str] = None,
    steps_count: Optional[int] = None,
    failed_count: Optional[int] = None,
    duration_ms: Optional[int] = None,
    error: Optional[str] = None,
):
    conn = _get_conn()
    fields = []
    args = []
    if status is not None:
        fields.append("status = ?")
        args.append(status)
    if final_answer is not None:
        fields.append("final_answer = ?")
        args.append(final_answer)
    if steps_count is not None:
        fields.append("steps_count = ?")
        args.append(steps_count)
    if failed_count is not None:
        fields.append("failed_count = ?")
        args.append(failed_count)
    if duration_ms is not None:
        fields.append("duration_ms = ?")
        args.append(duration_ms)
    if error is not None:
        fields.append("error = ?")
        args.append(error)
    if fields:
        args.append(run_id)
        conn.execute(f"UPDATE runs SET {', '.join(fields)} WHERE id = ?", args)
        conn.commit()


def add_step(
    run_id: int,
    step_num: int,
    action: str,
    argument: str,
    status: str,
    ai_reasoning: str,
    observation: str,
    duration_ms: int,
    model_name: str,
    screenshot_base64: Optional[str] = None,
) -> Optional[str]:
    """
    Save a step and optionally store its screenshot to disk.
    Returns the screenshot path if saved, else None.
    """
    conn = _get_conn()
    screenshot_path = None

    if screenshot_base64:
        import base64 as _b64
        run_dir = SCREENSHOTS_DIR / str(run_id)
        run_dir.mkdir(exist_ok=True)
        path = run_dir / f"step_{step_num}.png"
        try:
            path.write_bytes(_b64.b64decode(screenshot_base64))
            screenshot_path = str(path)
        except Exception:
            screenshot_path = None

    cursor = conn.execute(
        """INSERT INTO steps
           (run_id, step_num, action, argument, status, screenshot_path,
            ai_reasoning, observation, duration_ms, model_name)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            run_id, step_num, action, argument, status, screenshot_path,
            ai_reasoning, observation, duration_ms, model_name,
        ),
    )
    conn.commit()
    return screenshot_path


def get_run(run_id: int) -> Optional[dict]:
    conn = _get_conn()
    row = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
    if not row:
        return None
    return dict(row)


def get_run_by_session(session_id: str) -> Optional[dict]:
    conn = _get_conn()
    row = conn.execute(
        "SELECT * FROM runs WHERE session_id = ?", (session_id,)
    ).fetchone()
    if not row:
        return None
    return dict(row)


def list_runs(limit: int = 50, status: Optional[str] = None) -> list[dict]:
    conn = _get_conn()
    if status:
        rows = conn.execute(
            """SELECT id, session_id, task, url, mode, status, steps_count,
                      failed_count, created_at, duration_ms, error, final_answer
               FROM runs WHERE status = ?
               ORDER BY created_at DESC LIMIT ?""",
            (status, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            """SELECT id, session_id, task, url, mode, status, steps_count,
                      failed_count, created_at, duration_ms, error, final_answer
               FROM runs ORDER BY created_at DESC LIMIT ?""",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_steps(run_id: int) -> list[dict]:
    conn = _get_conn()
    rows = conn.execute(
        """SELECT step_num, action, argument, status, screenshot_path,
                  ai_reasoning, observation, duration_ms, model_name
           FROM steps WHERE run_id = ? ORDER BY step_num""",
        (run_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def get_screenshot(run_id: int, step_num: int) -> Optional[bytes]:
    path = SCREENSHOTS_DIR / str(run_id) / f"step_{step_num}.png"
    if path.exists():
        return path.read_bytes()
    return None


def delete_run(run_id: int):
    conn = _get_conn()
    # Screenshots cleaned up separately if needed
    import shutil
    run_dir = SCREENSHOTS_DIR / str(run_id)
    if run_dir.exists():
        shutil.rmtree(run_dir)
    conn.execute("DELETE FROM steps WHERE run_id = ?", (run_id,))
    conn.execute("DELETE FROM runs WHERE id = ?", (run_id,))
    conn.commit()


# Initialize on import
init_db()
