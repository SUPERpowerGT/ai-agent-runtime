from __future__ import annotations

import ast
from pathlib import Path
import re

from infrastructure.retrieval.rag.models import DocumentChunk


def chunk_documents(documents: list[dict], chunk_size: int = 800, overlap: int = 120) -> list[DocumentChunk]:
    chunks: list[DocumentChunk] = []

    for document in documents:
        text = document["text"].strip()
        source = document["source"]
        suffix = Path(source).suffix.lower()

        if not text:
            continue

        segments = _split_into_segments(text, source)
        if suffix == ".py":
            chunks.extend(_build_atomic_chunks(source, text, segments))
            continue

        current_text_parts: list[str] = []
        current_start = 0
        current_end = 0
        chunk_index = 0

        for segment in segments:
            segment_start = segment["start_offset"]
            segment_end = segment["end_offset"]
            segment_text = segment["text"]
            proposed_text = "".join(current_text_parts) + segment_text

            if current_text_parts and len(proposed_text) > chunk_size:
                chunk_text = "".join(current_text_parts).strip()
                if chunk_text:
                    start_offset = current_start
                    end_offset = current_end
                    chunks.append(
                        DocumentChunk(
                            source=source,
                            chunk_id=f"{source}#chunk-{chunk_index}",
                            text=chunk_text,
                            start_offset=start_offset,
                            end_offset=end_offset,
                            start_line=_offset_to_line_number(text, start_offset),
                            end_line=_offset_to_line_number(text, end_offset),
                            chunk_type="paragraph_group",
                            language=_detect_language_from_suffix(suffix),
                        )
                    )
                    chunk_index += 1

                overlap_text = chunk_text[-overlap:] if overlap > 0 and chunk_text else ""
                overlap_start = max(start_offset, end_offset - len(overlap_text)) if overlap_text else segment_start
                current_text_parts = [overlap_text, segment_text] if overlap_text else [segment_text]
                current_start = overlap_start
                current_end = segment_end
                continue

            if not current_text_parts:
                current_start = segment_start

            current_text_parts.append(segment_text)
            current_end = segment_end

        final_chunk = "".join(current_text_parts).strip()
        if final_chunk:
            chunks.append(
                DocumentChunk(
                    source=source,
                    chunk_id=f"{source}#chunk-{chunk_index}",
                    text=final_chunk,
                    start_offset=current_start,
                    end_offset=current_end,
                    start_line=_offset_to_line_number(text, current_start),
                    end_line=_offset_to_line_number(text, current_end),
                    chunk_type="paragraph_group",
                    language=_detect_language_from_suffix(suffix),
                )
            )

    return chunks


def _build_atomic_chunks(
    source: str,
    text: str,
    segments: list[dict],
) -> list[DocumentChunk]:
    chunks: list[DocumentChunk] = []
    suffix = Path(source).suffix.lower()

    for chunk_index, segment in enumerate(segments):
        start_offset = segment["start_offset"]
        end_offset = segment["end_offset"]
        segment_text = segment["text"]
        chunk_text = segment_text.strip()
        if not chunk_text:
            continue

        chunks.append(
            DocumentChunk(
                source=source,
                chunk_id=f"{source}#chunk-{chunk_index}",
                text=chunk_text,
                start_offset=start_offset,
                end_offset=end_offset,
                start_line=_offset_to_line_number(text, start_offset),
                end_line=_offset_to_line_number(text, end_offset),
                chunk_type=segment.get("chunk_type", "atomic"),
                language=segment.get("language", _detect_language_from_suffix(suffix)),
                symbol_name=segment.get("symbol_name"),
                symbol_kind=segment.get("symbol_kind"),
                section_title=segment.get("section_title"),
            )
        )

    return chunks


def _split_into_segments(text: str, source: str) -> list[dict]:
    suffix = Path(source).suffix.lower()

    if suffix == ".py":
        python_segments = _split_python_segments(text)
        if python_segments:
            return python_segments

    if suffix == ".md":
        markdown_segments = _split_markdown_segments(text)
        if markdown_segments:
            return markdown_segments

    return _split_paragraph_segments(text)


def _split_python_segments(text: str) -> list[tuple[int, int, str]]:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []

    line_offsets = _compute_line_offsets(text)
    top_level_nodes = [
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        and getattr(node, "lineno", None) is not None
        and getattr(node, "end_lineno", None) is not None
    ]
    if not top_level_nodes:
        return []

    segments: list[dict] = []
    cursor = 0

    for node in top_level_nodes:
        start_offset = _line_to_offset(line_offsets, node.lineno, default=0)
        end_offset = _line_to_offset(line_offsets, node.end_lineno + 1, default=len(text))

        if start_offset > cursor:
            prefix_text = text[cursor:start_offset]
            if prefix_text.strip():
                segments.append({
                    "start_offset": cursor,
                    "end_offset": start_offset,
                    "text": prefix_text,
                    "chunk_type": "module_prelude",
                    "language": "python",
                })

        segment_text = text[start_offset:end_offset]
        if segment_text.strip():
            symbol_kind = "class" if isinstance(node, ast.ClassDef) else "function"
            segments.append({
                "start_offset": start_offset,
                "end_offset": end_offset,
                "text": segment_text,
                "chunk_type": symbol_kind,
                "language": "python",
                "symbol_name": node.name,
                "symbol_kind": symbol_kind,
            })

        cursor = end_offset

    if cursor < len(text):
        tail_text = text[cursor:]
        if tail_text.strip():
            segments.append({
                "start_offset": cursor,
                "end_offset": len(text),
                "text": tail_text,
                "chunk_type": "module_tail",
                "language": "python",
            })

    return segments


def _split_markdown_segments(text: str) -> list[dict]:
    heading_pattern = re.compile(r"(?m)^#{1,6}\s+")
    matches = list(heading_pattern.finditer(text))
    if not matches:
        return []

    segments: list[dict] = []
    starts = [match.start() for match in matches]

    if starts[0] > 0:
        prefix = text[:starts[0]]
        if prefix.strip():
            segments.append({
                "start_offset": 0,
                "end_offset": starts[0],
                "text": prefix,
                "chunk_type": "markdown_prelude",
                "section_title": None,
            })

    for index, start in enumerate(starts):
        end = starts[index + 1] if index + 1 < len(starts) else len(text)
        segment_text = text[start:end]
        if segment_text.strip():
            section_title = _extract_markdown_heading(segment_text)
            segments.append({
                "start_offset": start,
                "end_offset": end,
                "text": segment_text,
                "chunk_type": "markdown_section",
                "section_title": section_title,
            })

    return segments


def _split_paragraph_segments(text: str) -> list[dict]:
    segments: list[dict] = []

    for match in re.finditer(r".*?(?:\n\s*\n|\Z)", text, flags=re.DOTALL):
        segment_text = match.group(0)
        if not segment_text.strip():
            continue
        segments.append({
            "start_offset": match.start(),
            "end_offset": match.end(),
            "text": segment_text,
            "chunk_type": "paragraph",
        })

    if not segments:
        return [{
            "start_offset": 0,
            "end_offset": len(text),
            "text": text,
            "chunk_type": "paragraph",
        }]

    return segments


def _offset_to_line_number(text: str, offset: int) -> int:
    clamped_offset = max(0, min(len(text), offset))
    return text.count("\n", 0, clamped_offset) + 1


def _compute_line_offsets(text: str) -> list[int]:
    offsets = [0]
    for index, char in enumerate(text):
        if char == "\n":
            offsets.append(index + 1)
    return offsets


def _line_to_offset(line_offsets: list[int], line_number: int, *, default: int) -> int:
    index = max(1, line_number) - 1
    if 0 <= index < len(line_offsets):
        return line_offsets[index]
    return default


def _detect_language_from_suffix(suffix: str) -> str | None:
    mapping = {
        ".py": "python",
        ".js": "javascript",
        ".ts": "typescript",
        ".md": "markdown",
        ".txt": "text",
        ".json": "json",
        ".yaml": "yaml",
        ".yml": "yaml",
    }
    return mapping.get(suffix)


def _extract_markdown_heading(text: str) -> str | None:
    first_line = text.strip().splitlines()[0] if text.strip() else ""
    match = re.match(r"^#{1,6}\s+(.+)$", first_line)
    if not match:
        return None
    return match.group(1).strip()
