from __future__ import annotations

from pathlib import Path

from .chunking import chunk_text
from .extract import extract_session_notes
from .semalingua import render_session_semalingua
from .smart_extract import extract_session_notes_smart
from .transcripts import parse_openclaw_jsonl, transcript_to_blocks


def ingest_session_file(store, path: Path, extract_mode: str = 'raw') -> bool:
    turns = parse_openclaw_jsonl(path)
    if not turns:
        return False

    blocks = transcript_to_blocks(turns)
    raw_text = "\n\n".join(blocks)
    if extract_mode == 'smart':
        notes = extract_session_notes_smart(turns)
    else:
        notes = extract_session_notes(turns)
        notes['mode'] = 'raw'
    sl_text = render_session_semalingua(str(path), notes)

    raw_chunks = []
    for block in blocks:
        raw_chunks.extend(chunk_text(block, max_chars=1000, overlap=100))

    store.upsert_document(str(path), "transcript", raw_text, chunks=raw_chunks)
    store.upsert_document(
        str(path) + "#semalingua",
        "session_note",
        sl_text,
        chunks=chunk_text(sl_text, max_chars=800, overlap=80),
    )
    return True
