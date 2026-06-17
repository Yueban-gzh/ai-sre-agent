"""MCP Server: exposes SRE diagnosis tools via Model Context Protocol."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from mcp.server.fastmcp import FastMCP
from pydantic import Field

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agent.scenario import RUNBOOKS_DIR, Scenario, get_scenario
from mcp_server.git_helper import get_recent_changes
from mcp_server.rag import search_runbooks

mcp = FastMCP("sre-diagnosis-tools")


def active_scenario() -> Scenario:
    return get_scenario(os.environ.get("SRE_SCENARIO"))


def normalize_repo_path(file_path: str, repo_dir: Path) -> str:
    normalized = file_path.replace("\\", "/").lstrip("/")
    repo_prefix = str(repo_dir.relative_to(PROJECT_ROOT)).replace("\\", "/") + "/"
    if normalized.startswith(repo_prefix):
        normalized = normalized[len(repo_prefix) :]
    legacy = "fixtures/repo/"
    if normalized.startswith(legacy):
        normalized = normalized[len(legacy) :]
    return normalized


@mcp.tool()
def read_logs(
    file_name: str = Field(description="Log file name, e.g. app_error.log or cache_error.log"),
    filter_keyword: str = Field(default="", description="Optional keyword filter"),
) -> str:
    """Read application error logs for the active incident scenario."""
    sc = active_scenario()
    log_path = sc.logs_dir / file_name
    if not log_path.exists():
        available = [p.name for p in sc.logs_dir.glob("*.log")]
        return json.dumps(
            {
                "scenario": sc.name,
                "error": f"Log file not found: {file_name}",
                "available": available,
                "hint": sc.default_log,
            },
            ensure_ascii=False,
        )

    lines = log_path.read_text(encoding="utf-8").splitlines()
    if filter_keyword:
        keyword = filter_keyword.lower()
        lines = [line for line in lines if keyword in line.lower()]

    return json.dumps(
        {
            "scenario": sc.name,
            "file": file_name,
            "line_count": len(lines),
            "content": "\n".join(lines),
        },
        ensure_ascii=False,
    )


@mcp.tool()
def git_recent_changes(
    hours: int = Field(default=24, ge=1, le=168, description="Hours to look back"),
) -> str:
    """Query recent code changes — real git log with fixture fallback."""
    sc = active_scenario()
    payload = get_recent_changes(PROJECT_ROOT, sc.git_fixture, hours)
    payload["scenario"] = sc.name
    return json.dumps(payload, ensure_ascii=False, indent=2)


@mcp.tool()
def query_runbook(
    keyword: str = Field(description="Search query for runbook RAG retrieval"),
    top_k: int = Field(default=3, ge=1, le=5, description="Top-k chunks to return"),
) -> str:
    """Retrieve ranked runbook chunks via chunk-based BM25 RAG."""
    sc = active_scenario()
    chunks = search_runbooks(RUNBOOKS_DIR, keyword, top_k=top_k)

    if not chunks:
        available = [p.name for p in RUNBOOKS_DIR.glob("*.md")]
        return json.dumps(
            {
                "scenario": sc.name,
                "query": keyword,
                "retrieval_method": "chunked_bm25_rag",
                "chunks": [],
                "available_runbooks": available,
            },
            ensure_ascii=False,
        )

    return json.dumps(
        {
            "scenario": sc.name,
            "query": keyword,
            "retrieval_method": "chunked_bm25_rag",
            "chunk_count": len(chunks),
            "chunks": chunks,
            "note": "Verify all fixes with run_tests — hotfixes may stop 500s but fail unit tests",
        },
        ensure_ascii=False,
        indent=2,
    )


@mcp.tool()
def read_source(
    file_path: str = Field(description="Source file in scenario repo, e.g. db_query.py or user_cache.py"),
) -> str:
    """Read source code from the active scenario repository."""
    sc = active_scenario()
    rel = normalize_repo_path(file_path, sc.repo_dir)
    target = (sc.repo_dir / rel).resolve()
    if not str(target).startswith(str(sc.repo_dir.resolve())):
        return json.dumps({"error": "Path traversal not allowed"}, ensure_ascii=False)

    if not target.exists():
        available = [p.name for p in sc.repo_dir.glob("*.py")]
        return json.dumps(
            {
                "scenario": sc.name,
                "error": f"File not found: {file_path}",
                "use_path_like": sc.primary_source,
                "available": available,
            },
            ensure_ascii=False,
        )

    content = target.read_text(encoding="utf-8")
    return json.dumps(
        {"scenario": sc.name, "file": rel, "line_count": len(content.splitlines()), "content": content},
        ensure_ascii=False,
    )


@mcp.tool()
def apply_patch(
    file_path: str = Field(description="Source file in scenario repo"),
    search: str = Field(description="Exact code snippet to find"),
    replace: str = Field(description="Replacement snippet"),
) -> str:
    """Apply a targeted code patch in the active scenario repository."""
    sc = active_scenario()
    rel = normalize_repo_path(file_path, sc.repo_dir)
    target = (sc.repo_dir / rel).resolve()
    if not str(target).startswith(str(sc.repo_dir.resolve())):
        return json.dumps({"error": "Path traversal not allowed"}, ensure_ascii=False)

    if not target.exists():
        available = [p.name for p in sc.repo_dir.glob("*.py")]
        return json.dumps(
            {
                "scenario": sc.name,
                "error": f"File not found: {file_path}",
                "use_path_like": sc.primary_source,
                "available": available,
            },
            ensure_ascii=False,
        )

    original = target.read_text(encoding="utf-8")
    if search not in original:
        return json.dumps(
            {
                "error": "Search snippet not found in file",
                "file": rel,
                "hint": "Call read_source first for exact content",
            },
            ensure_ascii=False,
        )

    updated = original.replace(search, replace, 1)
    target.write_text(updated, encoding="utf-8")
    return json.dumps(
        {"scenario": sc.name, "status": "patched", "file": rel, "bytes_changed": len(updated) - len(original)},
        ensure_ascii=False,
    )


@mcp.tool()
def run_tests(
    test_path: str = Field(default="", description="Pytest path relative to project root (empty = scenario default)"),
) -> str:
    """Run pytest to verify the fix for the active scenario."""
    sc = active_scenario()
    target = test_path or sc.test_path
    allowed = sc.allowed_test_paths

    if target not in allowed:
        return json.dumps(
            {
                "scenario": sc.name,
                "error": "Test path not allowed",
                "allowed_paths": sorted(allowed),
                "default": sc.test_path,
            },
            ensure_ascii=False,
        )

    result = subprocess.run(
        [sys.executable, "-m", "pytest", target, "-v", "--tb=short", "-q"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=60,
        stdin=subprocess.DEVNULL,
    )

    return json.dumps(
        {
            "scenario": sc.name,
            "test_path": target,
            "exit_code": result.returncode,
            "passed": result.returncode == 0,
            "stdout": result.stdout,
            "stderr": result.stderr,
        },
        ensure_ascii=False,
    )


@mcp.tool()
def list_scenario_info() -> str:
    """Return metadata about the active incident scenario (tools, paths, primary source file)."""
    sc = active_scenario()
    return json.dumps(
        {
            "name": sc.name,
            "display_name": sc.display_name,
            "description": sc.description,
            "default_log": sc.default_log,
            "primary_source": sc.primary_source,
            "test_path": sc.test_path,
            "repo_dir": str(sc.repo_dir.relative_to(PROJECT_ROOT)),
        },
        ensure_ascii=False,
        indent=2,
    )


if __name__ == "__main__":
    mcp.run(transport="stdio")
