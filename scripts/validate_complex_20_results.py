#!/usr/bin/env python3
"""Quality gate for complex 20-task benchmark artifacts."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "screenshots_complex_20" / "results_complex_20.json"
THRESHOLD = 0.85

CATEGORY_SIGNALS = {
    "search": ["search", "result", "title"],
    "signup": ["sign", "join", "register", "account"],
    "auth": ["login", "password", "username", "sign in"],
    "ecommerce": ["cart", "price", "product", "buy"],
    "travel": ["hotel", "flight", "stay", "booking", "listing"],
    "jobs": ["job", "apply", "role", "salary", "company"],
    "research": ["article", "question", "answer", "summary"],
    "media": ["video", "channel", "watch", "title"],
    "forms": ["form", "sign", "submit", "field"],
}


def main() -> int:
    if not RESULTS.exists():
        print(json.dumps({"ok": False, "skipped": True, "error": f"missing file: {RESULTS}"}))
        return 0

    payload = json.loads(RESULTS.read_text())
    results = payload.get("results", [])
    total = len(results)
    if total < 20:
        print(json.dumps({"ok": False, "error": f"expected >=20 tasks, got {total}"}))
        return 2

    intent_pass = 0
    screenshot_pass = 0
    checks = []

    for r in results:
        cat = (r.get("category") or "").lower()
        ans = (r.get("answer") or "").lower()
        status = (r.get("status") or "").lower()
        signals = CATEGORY_SIGNALS.get(cat, ["page", "title"])
        hit = any(s in ans for s in signals)
        status_ok = status in {"passed", "partial", "completed"}
        intent_ok = hit or status_ok

        ss = r.get("screenshot") or ""
        ss_ok = bool(ss) and Path(ss).exists()

        if intent_ok:
            intent_pass += 1
        if ss_ok:
            screenshot_pass += 1

        checks.append({
            "idx": r.get("idx"),
            "name": r.get("name"),
            "category": cat,
            "status": status,
            "intent_ok": intent_ok,
            "screenshot_ok": ss_ok,
        })

    intent_rate = intent_pass / total
    screenshot_rate = screenshot_pass / total
    ok = intent_rate >= THRESHOLD and screenshot_rate >= THRESHOLD

    out = {
        "ok": ok,
        "threshold": THRESHOLD,
        "total": total,
        "intent_pass": intent_pass,
        "intent_rate": round(intent_rate * 100, 2),
        "screenshot_pass": screenshot_pass,
        "screenshot_rate": round(screenshot_rate * 100, 2),
        "checks": checks,
    }

    out_path = ROOT / "screenshots_complex_20" / "validation_complex_20.json"
    out_path.write_text(json.dumps(out, indent=2))
    print(json.dumps(out))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
