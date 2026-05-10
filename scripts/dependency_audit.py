#!/usr/bin/env python3
"""Dependency drift audit using project-local environments."""
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND_PIP = ROOT / 'backend' / 'venv' / 'bin' / 'pip'
OUT = ROOT / 'screenshots_live_test_100' / 'dependency_audit.json'  # CI artifact path


def run(cmd, cwd=None):
    p = subprocess.run(cmd, cwd=cwd, text=True, capture_output=True)
    return {"code": p.returncode, "stdout": p.stdout, "stderr": p.stderr}


def main():
    py = {"error": "backend pip not found", "packages": []}
    if BACKEND_PIP.exists():
        r = run([str(BACKEND_PIP), 'list', '--outdated', '--format=json'])
        if r['code'] == 0:
            try:
                py = {"packages": json.loads(r['stdout'] or '[]')}
            except Exception as e:
                py = {"error": f"json parse failed: {e}", "raw": r['stdout'][:2000]}
        else:
            py = {"error": r['stderr'][:2000], "raw": r['stdout'][:2000]}

    npm = {"error": "unknown", "packages": []}
    nr = run(['npm', 'outdated', '--json'], cwd=str(ROOT))
    if nr['code'] in (0, 1):
        try:
            npm_raw = json.loads(nr['stdout'] or '{}')
            npm = {"packages": npm_raw}
        except Exception as e:
            npm = {"error": f"json parse failed: {e}", "raw": nr['stdout'][:2000]}
    else:
        npm = {"error": nr['stderr'][:2000], "raw": nr['stdout'][:2000]}

    out = {
        "python_outdated_count": len(py.get('packages', [])) if isinstance(py.get('packages', []), list) else -1,
        "npm_outdated_count": len(npm.get('packages', {})) if isinstance(npm.get('packages', {}), dict) else -1,
        "python": py,
        "npm": npm,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2))
    print(json.dumps({"artifact": str(OUT), "python_outdated_count": out["python_outdated_count"], "npm_outdated_count": out["npm_outdated_count"]}))


if __name__ == '__main__':
    main()
