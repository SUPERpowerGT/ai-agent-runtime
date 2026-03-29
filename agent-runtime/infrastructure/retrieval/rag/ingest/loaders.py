from __future__ import annotations

from pathlib import Path


SUPPORTED_EXTENSIONS = {".txt", ".md", ".py", ".json", ".yaml", ".yml"}


def load_supported_documents(file_paths: list[str]) -> list[dict]:
    documents: list[dict] = []

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
