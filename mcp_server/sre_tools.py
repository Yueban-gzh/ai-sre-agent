"""MCP Server: exposes SRE diagnosis tools via Model Context Protocol."""

from __future__ import annotations

import ast
import difflib
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


def is_path_within(target: Path, root: Path) -> bool:
    """目标路径解析后必须位于指定根目录内。"""
    try:
        target.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def subprocess_text(value: str | bytes | None) -> str:
    """将 subprocess 输出统一转换为可序列化字符串。"""
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def normalize_repo_path(file_path: str, repo_dir: Path) -> str:
    normalized = file_path.replace("\\", "/").lstrip("/")

    try:
        repo_prefix = str(repo_dir.relative_to(PROJECT_ROOT)).replace("\\", "/") + "/"
    except ValueError:
        # pytest 的临时目录可能不在 PROJECT_ROOT 下
        repo_prefix = ""

    if repo_prefix and normalized.startswith(repo_prefix):
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
    if not is_path_within(target, sc.repo_dir):
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
    """Apply one auditable, syntax-checked patch."""
    sc = active_scenario()
    rel = normalize_repo_path(file_path, sc.repo_dir)
    target = (sc.repo_dir / rel).resolve()

    if not is_path_within(target, sc.repo_dir):
        return json.dumps(
            {
                "scenario": sc.name,
                "status": "rejected",
                "error": "Path traversal not allowed",
            },
            ensure_ascii=False,
        )

    if not target.exists() or not target.is_file():
        available = [p.name for p in sc.repo_dir.glob("*.py")]
        return json.dumps(
            {
                "scenario": sc.name,
                "status": "rejected",
                "error": f"File not found: {file_path}",
                "use_path_like": sc.primary_source,
                "available": available,
            },
            ensure_ascii=False,
        )

    if not search:
        return json.dumps(
            {
                "scenario": sc.name,
                "status": "rejected",
                "error": "Search snippet must not be empty",
                "file": rel,
            },
            ensure_ascii=False,
        )

    original = target.read_text(encoding="utf-8")
    match_count = original.count(search)

    if match_count == 0:
        return json.dumps(
            {
                "scenario": sc.name,
                "status": "rejected",
                "error": "Search snippet not found in file",
                "file": rel,
                "hint": "Call read_source first for exact content",
            },
            ensure_ascii=False,
        )

    if match_count > 1:
        return json.dumps(
            {
                "scenario": sc.name,
                "status": "rejected",
                "error": "Search snippet is ambiguous",
                "file": rel,
                "match_count": match_count,
                "hint": "Provide a longer, unique snippet",
            },
            ensure_ascii=False,
        )

    updated = original.replace(search, replace, 1)

    if target.suffix == ".py":
        try:
            ast.parse(updated, filename=rel)
        except SyntaxError as exc:
            return json.dumps(
                {
                    "scenario": sc.name,
                    "status": "rejected",
                    "error": "Patch introduces invalid Python syntax",
                    "file": rel,
                    "line": exc.lineno,
                    "offset": exc.offset,
                    "detail": exc.msg,
                },
                ensure_ascii=False,
            )

    diff = "\n".join(
        difflib.unified_diff(
            original.splitlines(),
            updated.splitlines(),
            fromfile=f"a/{rel}",
            tofile=f"b/{rel}",
            lineterm="",
        )
    )

    temp_path = target.with_name(f".{target.name}.tmp")
    try:
        temp_path.write_text(updated, encoding="utf-8")
        os.replace(temp_path, target)
    finally:
        temp_path.unlink(missing_ok=True)

    return json.dumps(
        {
            "scenario": sc.name,
            "status": "patched",
            "file": rel,
            "match_count": match_count,
            "bytes_changed": len(updated.encode("utf-8")) - len(original.encode("utf-8")),
            "diff": diff,
        },
        ensure_ascii=False,
        indent=2,
    )


@mcp.tool()
def run_tests(
    test_path: str = Field(
        default="",
        description="Pytest path relative to project root (empty = scenario default)",
    ),
) -> str:
    """Run an allow-listed pytest target and always return structured output."""
    sc = active_scenario()
    target = (test_path or sc.test_path).replace("\\", "/")
    allowed = {path.replace("\\", "/") for path in sc.allowed_test_paths}

    if target not in allowed:
        return json.dumps(
            {
                "scenario": sc.name,
                "test_path": target,
                "passed": False,
                "error": "Test path not allowed",
                "error_type": "ValidationError",
                "allowed_paths": sorted(allowed),
                "default": sc.test_path,
            },
            ensure_ascii=False,
        )

    command = [
        sys.executable,
        "-m",
        "pytest",
        target,
        "-v",
        "--tb=short",
        "-q",
    ]

    try:
        result = subprocess.run(
            command,
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=60,
            stdin=subprocess.DEVNULL,
        )

    except subprocess.TimeoutExpired as exc:
        return json.dumps(
            {
                "scenario": sc.name,
                "test_path": target,
                "command": command,
                "exit_code": None,
                "passed": False,
                "timed_out": True,
                "error_type": "TimeoutExpired",
                "error": "Pytest exceeded the 60-second timeout",
                "stdout": subprocess_text(exc.stdout),
                "stderr": subprocess_text(exc.stderr),
            },
            ensure_ascii=False,
        )

    except OSError as exc:
        return json.dumps(
            {
                "scenario": sc.name,
                "test_path": target,
                "command": command,
                "exit_code": None,
                "passed": False,
                "timed_out": False,
                "error_type": type(exc).__name__,
                "error": str(exc),
                "stdout": "",
                "stderr": "",
            },
            ensure_ascii=False,
        )

    return json.dumps(
        {
            "scenario": sc.name,
            "test_path": target,
            "command": command,
            "exit_code": result.returncode,
            "passed": result.returncode == 0,
            "timed_out": False,
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
