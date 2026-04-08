from __future__ import annotations


def chunk_text(text: str, max_chars: int = 1200, overlap: int = 120):
    text = text.strip()
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]

    chunks = []
    start = 0
    n = len(text)
    while start < n:
        end = min(start + max_chars, n)
        if end < n:
            split = text.rfind('\n\n', start, end)
            if split <= start:
                split = text.rfind('\n', start, end)
            if split > start + 200:
                end = split
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= n:
            break
        start = max(end - overlap, start + 1)
    return chunks
