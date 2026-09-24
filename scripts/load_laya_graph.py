"""Load reports/laya_task_graph.json into Laya through the Founder API.

Each task is created with its dependencies and then driven toward its target
status through Laya's real transitions, attaching the recorded evidence. Laya
enforces the gates, so a claimed status is only reached when its evidence and
dependencies satisfy them; any rejection is reported, never overridden.

Requires a founder access token (TOTP-verified where MFA applies) supplied via
the ARIMA_FOUNDER_TOKEN environment variable. Local targets only unless
--allow-remote is given.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from urllib.parse import urlsplit

import httpx

PATHS = {
    "completed": ("ready", "running", "verifying", "passed", "completed"),
    "passed": ("ready", "running", "verifying", "passed"),
    "blocked": ("blocked",),
    "discovered": (),
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8765")
    parser.add_argument("--graph", default=str(Path(__file__).resolve().parents[1] / "reports/laya_task_graph.json"))
    parser.add_argument("--allow-remote", action="store_true")
    args = parser.parse_args()
    if urlsplit(args.base_url).hostname not in {"127.0.0.1", "localhost"} and not args.allow_remote:
        print("Refusing to write a task graph to a non-local API", file=sys.stderr)
        return 2
    token = os.environ.get("ARIMA_FOUNDER_TOKEN")
    if not token:
        print("ARIMA_FOUNDER_TOKEN is required", file=sys.stderr)
        return 2

    client = httpx.Client(base_url=args.base_url, timeout=30, headers={"Authorization": f"Bearer {token}"})

    def post(path: str, payload: dict | None = None) -> httpx.Response:
        csrf = client.post("/api/v1/auth/csrf").json()["csrf_token"]
        return client.post(path, json=payload, headers={"X-CSRF-Token": csrf})

    base = "/api/v1/admin/founder/laya/tasks"
    graph = json.loads(Path(args.graph).read_text())
    rejected: list[str] = []
    for task in graph["tasks"]:
        created = post(base, {
            "key": task["key"], "title": task["title"], "purpose": task["title"],
            "owner": task["owner"], "depends_on": task["depends_on"],
            "acceptance_criteria": task["acceptance_criteria"], "tests": task["tests"],
        })
        if created.status_code not in (201, 409):
            rejected.append(f"{task['key']}: create {created.status_code} {created.text[:120]}")
            continue
        for kind, reference in task.get("evidence", []):
            post(f"{base}/{task['key']}/evidence", {"kind": kind, "reference": reference})
        for status in PATHS[task["target"]]:
            payload = {"status": status}
            if status == "blocked":
                payload["blocker"] = task["blocker"]
            moved = post(f"{base}/{task['key']}/transition", payload)
            if moved.status_code != 200:
                rejected.append(f"{task['key']}: -> {status} rejected: {moved.json().get('detail')}")
                break
    summary = client.get("/api/v1/admin/founder/laya/graph").json()
    print(json.dumps({"laya_graph": summary, "rejected": rejected}, indent=2))
    return 1 if rejected else 0


if __name__ == "__main__":
    raise SystemExit(main())
