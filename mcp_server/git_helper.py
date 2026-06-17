"""Git history helper — real git log with fixture fallback for demo reliability."""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path


def _parse_git_timestamp(iso: str) -> datetime:
    # git --date=iso: 2026-06-17 15:44:40 +0800
    cleaned = iso.strip().rsplit(" ", 1)[0]
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(cleaned, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return datetime.now(timezone.utc)


def query_git_log(project_root: Path, hours: int) -> list[dict]:
    """Return recent commits from real git history."""
    cmd = [
        "git",
        "-C",
        str(project_root),
        "log",
        f"--since={hours} hours ago",
        "--pretty=format:%H|%an|%s|%ci",
        "--name-only",
    ]
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=15,
        stdin=subprocess.DEVNULL,
    )
    if result.returncode != 0:
        return []

    changes: list[dict] = []
    now = datetime.now(timezone.utc)
    current: dict | None = None

    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        if "|" in line and not line.startswith(" "):
            if current:
                changes.append(current)
            commit, author, message, committed_at = line.split("|", 3)
            committed = _parse_git_timestamp(committed_at)
            hours_ago = max(0, int((now - committed).total_seconds() // 3600))
            current = {
                "commit": commit[:7],
                "author": author,
                "hours_ago": hours_ago,
                "message": message,
                "files": [],
            }
        elif current is not None:
            current["files"].append(line.strip())

    if current:
        changes.append(current)

    return changes


def load_fixture_changes(fixture_file: Path, hours: int) -> list[dict]:
    if not fixture_file.exists():
        return []
    data = json.loads(fixture_file.read_text(encoding="utf-8"))
    return [c for c in data if c.get("hours_ago", 999) <= hours]


def get_recent_changes(project_root: Path, fixture_file: Path, hours: int) -> dict:
    """Prefer real git log; fall back to incident fixture when git is unavailable."""
    git_changes = query_git_log(project_root, hours)
    if git_changes:
        return {
            "hours": hours,
            "source": "git",
            "changes": git_changes,
        }

    fixture_changes = load_fixture_changes(fixture_file, hours)
    return {
        "hours": hours,
        "source": "fixture",
        "note": "No git history found — using incident simulation data",
        "changes": fixture_changes,
    }
