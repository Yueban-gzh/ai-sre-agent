"""Test RAG ranking for various queries."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mcp_server.rag import search_runbooks

queries = [
    "IndexError",
    "IndexError loop range",
    "HTTP 500 database connection pool",
]

for q in queries:
    print(f"QUERY: {q}")
    for r in search_runbooks(Path("fixtures/runbooks"), q, top_k=4):
        print(f"  {r['rank']}. {r['score']:.3f} [{r['section']}]")
    print()
