"""Create demo git history so git_recent_changes returns real commits."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def run(cmd: list[str]) -> None:
    subprocess.run(cmd, cwd=PROJECT_ROOT, check=True)


def main() -> None:
    git_dir = PROJECT_ROOT / ".git"
    if not git_dir.exists():
        run(["git", "init"])
        print("[GIT] Initialized repository")

    run(["git", "config", "user.email", "demo@sre-agent.local"])
    run(["git", "config", "user.name", "SRE Demo"])

    # Stage project files (respects .gitignore)
    run(["git", "add", "-A"])
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )
    if status.stdout.strip():
        run(["git", "commit", "-m", "chore: initialize AI SRE incident diagnosis agent demo"])
        print("[GIT] Created initial commit")
    else:
        print("[GIT] Nothing to commit — working tree clean")

    print("[GIT] git_recent_changes will now prefer real git log over fixture data")


if __name__ == "__main__":
    main()
