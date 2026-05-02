"""
domain_memory.py — Learns from successful browser tasks and injects context on domain revisit.

After 2+ successful tasks on the same domain, stores:
  - URL patterns that worked
  - CSS selectors that successfully clicked/filled
  - Action sequences that completed tasks
  - Success rate per domain

On revisit: injects learned context into the AI prompt so it doesn't relearn the site.
"""

import sqlite3
import json
import logging
import os
from typing import Optional
from pathlib import Path

logger = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(__file__), "domain_memory.db")


def _get_db() -> sqlite3.Connection:
    """Get or create the domain memory SQLite DB."""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS domain_heuristics (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            domain          TEXT NOT NULL,
            url_pattern     TEXT,
            selectors_used   TEXT NOT NULL DEFAULT '[]',
            actions_sequence TEXT NOT NULL DEFAULT '[]',
            task_type       TEXT,
            success_count    INTEGER NOT NULL DEFAULT 0,
            fail_count      INTEGER NOT NULL DEFAULT 0,
            last_task       TEXT,
            last_success    REAL,
            created_at      REAL NOT NULL,
            updated_at      REAL NOT NULL,
            UNIQUE(domain, url_pattern, task_type)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS selector_fingerprint (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            domain          TEXT NOT NULL,
            selector        TEXT NOT NULL,
            success_count   INTEGER NOT NULL DEFAULT 0,
            fail_count      INTEGER NOT NULL DEFAULT 0,
            element_tag     TEXT,
            element_type    TEXT,
            last_used       REAL,
            first_seen      REAL NOT NULL,
            UNIQUE(domain, selector)
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_domain ON domain_heuristics(domain)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_selector_domain ON selector_fingerprint(domain)
    """)
    conn.commit()
    return conn


def record_action(domain: str, url: str, selector: str, action_type: str,
                  success: bool, element_tag: str = "", element_type: str = ""):
    """Record a single action outcome for a domain."""
    import time
    now = time.time()
    conn = _get_db()
    try:
        # Upsert selector fingerprint
        conn.execute("""
            INSERT INTO selector_fingerprint (domain, selector, success_count, fail_count,
                                             element_tag, element_type, last_used, first_seen)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(domain, selector) DO UPDATE SET
                success_count = success_count + CASE WHEN ? THEN 1 ELSE 0 END,
                fail_count    = fail_count    + CASE WHEN NOT ? THEN 1 ELSE 0 END,
                last_used     = ?,
                element_tag   = COALESCE(NULLIF(?, ''), element_tag),
                element_type  = COALESCE(NULLIF(?, ''), element_type)
        """, (domain, selector,
              1 if success else 0, 0 if success else 1,
              element_tag, element_type, now, now,
              success, success, now,
              element_tag, element_type))
        conn.commit()
    finally:
        conn.close()


def record_task_complete(domain: str, url: str, task_type: str,
                         selectors_used: list, actions_sequence: list):
    """Record a completed task and update success rate."""
    import time
    now = time.time()
    conn = _get_db()
    try:
        conn.execute("""
            INSERT INTO domain_heuristics
                (domain, url_pattern, selectors_used, actions_sequence, task_type,
                 success_count, last_task, last_success, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?, ?)
            ON CONFLICT(domain, url_pattern, task_type) DO UPDATE SET
                selectors_used   = ?,
                actions_sequence= ?,
                success_count    = success_count + 1,
                last_task        = ?,
                last_success     = ?,
                updated_at       = ?
        """, (domain, url, json.dumps(selectors_used), json.dumps(actions_sequence),
              task_type, task_type[:100], now, now, now,
              json.dumps(selectors_used), json.dumps(actions_sequence),
              task_type[:100], now, now))
        conn.commit()
    finally:
        conn.close()


def get_domain_context(domain: str) -> Optional[dict]:
    """Get learned context for a domain if we have enough data (2+ visits).

    Returns a dict with selectors and patterns to inject into AI prompts.
    Returns None if domain is not yet learned.
    """
    conn = _get_db()
    try:
        # Get aggregate stats
        cursor = conn.execute("""
            SELECT
                COUNT(*) as visit_count,
                SUM(success_count) as total_successes,
                SUM(fail_count)    as total_fails,
                GROUP_CONCAT(DISTINCT task_type) as task_types
            FROM domain_heuristics
            WHERE domain = ?
        """, (domain,))
        row = cursor.fetchone()
        if not row or row[0] < 1:
            return None

        visit_count   = row[0] or 0
        total_success = row[1] or 0
        total_fails   = row[2] or 0
        task_types    = row[3] or ""

        # Get top-performing selectors (high success ratio)
        cursor = conn.execute("""
            SELECT selector, success_count, fail_count,
                   ROUND(CAST(success_count AS FLOAT) / (success_count + fail_count + 1), 2) as ratio,
                   element_tag, element_type
            FROM selector_fingerprint
            WHERE domain = ? AND (success_count + fail_count) >= 1
            ORDER BY ratio DESC, success_count DESC
            LIMIT 20
        """, (domain,))
        top_selectors = []
        for sel_row in cursor.fetchall():
            top_selectors.append({
                "selector":     sel_row[0],
                "success_rate": sel_row[2],
                "successes":    sel_row[1],
                "fails":        sel_row[2],
                "element_tag":  sel_row[3],
                "element_type": sel_row[4],
            })

        # Get common action sequences
        cursor = conn.execute("""
            SELECT actions_sequence, success_count
            FROM domain_heuristics
            WHERE domain = ? AND success_count > 0
            ORDER BY success_count DESC
            LIMIT 5
        """, (domain,))
        action_sequences = []
        for seq_row in cursor.fetchall():
            try:
                seq = json.loads(seq_row[0])
            except Exception:
                seq = []
            action_sequences.append({"steps": seq, "successes": seq_row[1]})

        success_rate = (total_success / (total_success + total_fails)) if (total_success + total_fails) > 0 else 0

        return {
            "domain":        domain,
            "visit_count":   visit_count,
            "success_rate":  round(success_rate, 3),
            "task_types":    [t for t in task_types.split(",") if t],
            "top_selectors": top_selectors[:15],
            "action_sequences": action_sequences,
            "learned":       visit_count >= 2,  # Only inject if we've visited 2+ times
        }
    finally:
        conn.close()


def inject_domain_context(prompt_text: str, domain: str) -> str:
    """Inject domain memory context into a prompt string if we have learned data."""
    ctx = get_domain_context(domain)
    if not ctx or not ctx.get("learned"):
        return prompt_text

    lines = [
        f"\n## DOMAIN MEMORY (visited {ctx['visit_count']}x, success_rate={ctx['success_rate']:.0%}):",
    ]

    if ctx["top_selectors"]:
        lines.append("Known-good selectors (use these first):")
        for sel in ctx["top_selectors"][:8]:
            tag = sel.get("element_tag", "")
            lines.append(f"  {tag}#{sel['selector'][:60]} — {sel['successes']} successes, {sel['fails']} fails")

    if ctx["action_sequences"]:
        lines.append("Successful action patterns:")
        for seq in ctx["action_sequences"][:3]:
            steps_str = " → ".join(str(s) for s in seq["steps"][:5])
            lines.append(f"  [{seq['successes']}x] {steps_str}")

    return prompt_text + "\n".join(lines)


# ── Convenience: called by action_history after each completed task ──────────────

def learn_from_completed_task(domain: str, url: str, task: str,
                               successful_selectors: list,
                               action_steps: list):
    """Called by BrowserAgent after a task completes to store learnings."""
    task_type = _classify_task(task)
    record_task_complete(domain, url, task_type, successful_selectors, action_steps)
    for sel in successful_selectors:
        record_action(domain, url, sel, task_type, success=True)


def _classify_task(task: str) -> str:
    """Coarse classification of task type for storage."""
    t = task.lower()
    if any(w in t for w in ["login", "sign in", "auth"]):
        return "login"
    if any(w in t for w in ["apply", "job", "resume", "career"]):
        return "job_application"
    if any(w in t for w in ["form", "fill", "register", "signup"]):
        return "form_fill"
    if any(w in t for w in ["search", "find", "look"]):
        return "search"
    if any(w in t for w in ["buy", "purchase", "checkout", "cart"]):
        return "commerce"
    return "general"
