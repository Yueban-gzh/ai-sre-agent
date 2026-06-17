"""Unit tests for chunk-based RAG retrieval (BM25)."""

from pathlib import Path

from mcp_server.rag import chunk_markdown, search_runbooks

RUNBOOKS = Path(__file__).resolve().parent.parent / "fixtures" / "runbooks"


def test_chunk_markdown_splits_sections():
    content = "# Title\n\n## Alpha\nline1\n\n## Beta\nline2"
    chunks = chunk_markdown(content, "test.md")
    sections = {c["section"] for c in chunks}
    assert "Alpha" in sections
    assert "Beta" in sections


def test_indexerror_query_ranks_hotfix_first():
    results = search_runbooks(RUNBOOKS, "IndexError", top_k=3)
    assert results
    assert "Quick Mitigation" in results[0]["section"]
    assert results[0]["score"] > 0


def test_keyerror_query_ranks_hotfix_first():
    results = search_runbooks(RUNBOOKS, "KeyError cache hotfix migration", top_k=3)
    assert results
    assert "keyerror" in results[0]["file"]
    assert "Quick Mitigation" in results[0]["section"]


def test_connection_pool_query_surfaces_pool_runbook():
    results = search_runbooks(RUNBOOKS, "HTTP 500 database connection pool", top_k=2)
    assert any("connection_pool" in r["file"] for r in results)
