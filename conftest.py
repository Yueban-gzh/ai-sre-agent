import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# Support imports from both incident repos
for repo in (
    ROOT / "fixtures" / "repo",
    ROOT / "fixtures" / "scenarios" / "keyerror" / "repo",
):
    if repo.exists():
        sys.path.insert(0, str(repo))
