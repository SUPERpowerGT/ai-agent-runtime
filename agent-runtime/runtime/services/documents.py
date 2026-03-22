from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import math
import re


SUPPORTED_EXTENSIONS = {".txt", ".md", ".py", ".json", ".yaml", ".yml"}


@dataclass
class DocumentChunk:
    source: str
    chunk_id: str
    text: str
    score: float = 0.0


def load_supported_documents(file_paths: list[str]) -> list[dict]:
    documents = []

    for file_path in file_paths:
        path = Path(file_path).expanduser()

        if not path.exists() or not path.is_file():
            continue

        if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue

        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            text = path.read_text(encoding="utf-8", errors="ignore")

        if not text.strip():
            continue

        documents.append({
            "source": str(path),
            "text": text,
        })

    return documents


def chunk_documents(documents: list[dict], chunk_size: int = 800, overlap: int = 120) -> list[DocumentChunk]:
    chunks: list[DocumentChunk] = []

    for document in documents:
        text = document["text"].strip()
        source = document["source"]

        start = 0
        chunk_index = 0
        while start < len(text):
            end = min(len(text), start + chunk_size)
            chunk_text = text[start:end].strip()

            if chunk_text:
                chunks.append(
                    DocumentChunk(
                        source=source,
                        chunk_id=f"{source}#chunk-{chunk_index}",
                        text=chunk_text,
                    )
                )

            if end >= len(text):
                break

            start = max(0, end - overlap)
            chunk_index += 1

    return chunks


def retrieve_relevant_chunks(query: str, documents: list[dict], top_k: int = 4) -> list[dict]:
    chunks = chunk_documents(documents)
    query_terms = _tokenize(query)

    if not query_terms:
        return []

    ranked_chunks: list[DocumentChunk] = []
    for chunk in chunks:
        chunk.score = _score_chunk(query_terms, chunk.text)
        if chunk.score > 0:
            ranked_chunks.append(chunk)

    ranked_chunks.sort(key=lambda chunk: chunk.score, reverse=True)

    return [
        {
            "source": chunk.source,
            "chunk_id": chunk.chunk_id,
            "score": round(chunk.score, 4),
            "text": chunk.text,
        }
        for chunk in ranked_chunks[:top_k]
    ]

def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-zA-Z_][a-zA-Z0-9_#+.-]*", text.lower())


def _score_chunk(query_terms: list[str], chunk_text: str) -> float:
    chunk_terms = _tokenize(chunk_text)
    if not chunk_terms:
        return 0.0

    chunk_term_set = set(chunk_terms)
    overlap = sum(1 for term in query_terms if term in chunk_term_set)
    if overlap == 0:
        return 0.0

    density_bonus = overlap / math.sqrt(len(chunk_terms))
    return overlap + density_bonus
