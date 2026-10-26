"""Publish docs/tasks/BACKLOG.md as GitHub Issues.

Usage:
    py scripts/create_github_issues.py            # dry run, prints what would be created
    GITHUB_TOKEN=... py scripts/create_github_issues.py --apply

The token needs `issues: write` on the repository. It is read from the environment
and never stored. Issues whose title already exists are skipped, so reruns are safe.
"""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO = os.environ.get("GITHUB_REPOSITORY", "thestronghearted/Pantry")
BACKLOG = Path(__file__).resolve().parent.parent / "docs" / "tasks" / "BACKLOG.md"
API = f"https://api.github.com/repos/{REPO}"

LABEL_COLOURS = {
    "mvp": "0e8a16",
    "stretch": "c5def5",
    "incident": "d93f0b",
    "needs-human": "b60205",
}


def parse(text: str) -> list[dict]:
    tasks = []
    for block in re.split(r"^## ", text, flags=re.M)[1:]:
        head, _, rest = block.partition("\n")
        m = re.match(r"(T\d+) — (.+)", head.strip())
        if not m:
            continue
        labels = re.search(r"^labels:\s*(.+)$", rest, re.M)
        spec = re.search(r"^spec:\s*(.+)$", rest, re.M)
        criteria = "\n".join(line for line in rest.splitlines() if line.startswith("- ["))
        body = (
            f"**Spec:** {spec.group(1) if spec else 'n/a'}\n\n"
            f"### Acceptance criteria\n{criteria}\n\n"
            f"_Backlog id {m.group(1)}. Process: docs/PROCESS.md._"
        )
        tasks.append(
            {
                "id": m.group(1),
                "title": f"{m.group(1)} {m.group(2)}",
                "labels": [s.strip() for s in labels.group(1).split(",")] if labels else [],
                "body": body,
            }
        )
    return tasks


def call(method: str, path: str, token: str, payload: dict | None = None):
    req = urllib.request.Request(
        API + path,
        method=method,
        data=json.dumps(payload).encode() if payload is not None else None,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read() or "null")


def main() -> int:
    tasks = parse(BACKLOG.read_text(encoding="utf-8"))
    apply = "--apply" in sys.argv
    if not apply:
        for t in tasks:
            print(f"[dry-run] {t['title']}  labels={t['labels']}")
        print(f"{len(tasks)} issues. Re-run with --apply and GITHUB_TOKEN set to create them.")
        return 0

    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        print("GITHUB_TOKEN is not set", file=sys.stderr)
        return 1

    existing_titles = set()
    page = 1
    while True:
        batch = call("GET", f"/issues?state=all&per_page=100&page={page}", token)
        if not batch:
            break
        existing_titles |= {i["title"] for i in batch}
        page += 1

    wanted = {label for t in tasks for label in t["labels"]}
    for label in sorted(wanted):
        try:
            call("POST", "/labels", token, {"name": label, "color": LABEL_COLOURS.get(label, "ededed")})
        except urllib.error.HTTPError as e:  # 422 = already exists
            if e.code != 422:
                raise

    for t in tasks:
        if t["title"] in existing_titles:
            print(f"skip   {t['title']}")
            continue
        issue = call("POST", "/issues", token, {"title": t["title"], "body": t["body"], "labels": t["labels"]})
        print(f"create #{issue['number']} {t['title']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
