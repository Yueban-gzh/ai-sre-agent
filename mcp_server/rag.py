"""Chunk-based runbook retrieval with BM25 relevance scoring (RAG)."""

from __future__ import annotations

import math
import re
from pathlib import Path

BM25_K1 = 1.5
BM25_B = 0.75


def tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9_]+", text.lower())


def chunk_markdown(content: str, filename: str) -> list[dict]:
    """Split a runbook into ## sections as retrieval chunks."""
    chunks: list[dict] = []
    current_section = "Overview"
    current_lines: list[str] = []

    for line in content.splitlines():
        if line.startswith("## "):
            if current_lines:
                chunks.append(
                    {
                        "file": filename,
                        "section": current_section,
                        "content": "\n".join(current_lines).strip(),
                    }
                )
            current_section = line[3:].strip()
            current_lines = [line]
        else:
            current_lines.append(line)

    if current_lines:
        chunks.append(
            {
                "file": filename,
                "section": current_section,
                "content": "\n".join(current_lines).strip(),
            }
        )

    return chunks


def load_runbook_chunks(runbooks_dir: Path) -> list[dict]:
    chunks: list[dict] = []
    for path in sorted(runbooks_dir.glob("*.md")):
        content = path.read_text(encoding="utf-8")
        chunks.extend(chunk_markdown(content, path.name))
    return chunks


def _bm25_score(
    query_tokens: list[str],
    doc_tokens: list[str],
    avg_dl: float,
    doc_freq: dict[str, int],
    total_docs: int,
) -> float:
    if not query_tokens or not doc_tokens:
        return 0.0

    dl = len(doc_tokens)
    tf_map: dict[str, int] = {}
    for token in doc_tokens:
        tf_map[token] = tf_map.get(token, 0) + 1

    score = 0.0
    for token in set(query_tokens):
        if token not in tf_map:
            continue
        tf = tf_map[token]
        df = doc_freq.get(token, 0)
        idf = math.log((total_docs - df + 0.5) / (df + 0.5) + 1.0)
        numer = tf * (BM25_K1 + 1)
        denom = tf + BM25_K1 * (1 - BM25_B + BM25_B * dl / avg_dl)
        score += idf * (numer / denom)

    return score


def search_runbooks(runbooks_dir: Path, query: str, top_k: int = 3) -> list[dict]:
    """Return top-k runbook chunks ranked by BM25 relevance."""
    all_chunks = load_runbook_chunks(runbooks_dir)
    if not all_chunks:
        return []

    query_tokens = tokenize(query)
    if not query_tokens:
        return []

    tokenized_docs: list[list[str]] = []
    doc_freq: dict[str, int] = {}
    for chunk in all_chunks:
        text = f"{chunk['section']} {chunk['content']}"
        tokens = tokenize(text)
        tokenized_docs.append(tokens)
        for token in set(tokens):
            doc_freq[token] = doc_freq.get(token, 0) + 1

    total_docs = len(all_chunks)
    avg_dl = sum(len(d) for d in tokenized_docs) / total_docs
    scored: list[tuple[float, dict]] = []

    for chunk, doc_tokens in zip(all_chunks, tokenized_docs):
        score = _bm25_score(query_tokens, doc_tokens, avg_dl, doc_freq, total_docs)

        section_lower = chunk["section"].lower()
        for token in query_tokens:
            if token in section_lower:
                score += 0.8

        if "quick mitigation" in section_lower:
            score += 1.0

        if score > 0:
            scored.append((score, chunk))

    scored.sort(key=lambda x: x[0], reverse=True)

    results = []
    for rank, (score, chunk) in enumerate(scored[:top_k], start=1):
        results.append(
            {
                "rank": rank,
                "score": round(score, 4),
                "file": chunk["file"],
                "section": chunk["section"],
                "content": chunk["content"],
                "citation": f"{chunk['file']}#{chunk['section']}",
            }
        )

    return results
