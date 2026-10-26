"""Open a GitHub issue for incidents that need a human. Only runs when a token and repository are configured."""
from __future__ import annotations

import logging
from pathlib import Path

import httpx

from .config import Settings

log = logging.getLogger("responder.escalation")


def open_issue(settings: Settings, title: str, report_path: Path | None) -> str | None:
    if not (settings.github_token and settings.github_repository):
        return None
    body = report_path.read_text(encoding="utf-8") if report_path and report_path.exists() else "See the incident report."
    try:
        r = httpx.post(
            f"https://api.github.com/repos/{settings.github_repository}/issues",
            headers={"Authorization": f"Bearer {settings.github_token}", "Accept": "application/vnd.github+json"},
            json={"title": title, "body": body, "labels": ["incident", "needs-human"]},
            timeout=10.0,
        )
        r.raise_for_status()
        return r.json().get("html_url")
    except httpx.HTTPError:
        log.exception("could not open escalation issue")
        return None
