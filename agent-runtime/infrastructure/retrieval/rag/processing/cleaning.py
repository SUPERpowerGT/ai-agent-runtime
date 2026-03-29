from __future__ import annotations

import re


def clean_documents(documents: list[dict]) -> list[dict]:
    cleaned_documents: list[dict] = []

    for document in documents:
        text = document.get("text", "")
        cleaned_text = clean_text(text)
        if not cleaned_text:
            continue

        cleaned_documents.append({
            **document,
            "text": cleaned_text,
        })

    return cleaned_documents


def clean_text(text: str) -> str:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    normalized = re.sub(r"[ \t]+\n", "\n", normalized)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    return normalized.strip()
