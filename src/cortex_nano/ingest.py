from pathlib import Path

from .chunking import chunk_text
from .session_ingest import ingest_session_file

TEXT_EXTS = {".md", ".txt", ".jsonl", ".json", ".py", ".js", ".ts", ".php", ".yaml", ".yml"}


def detect_kind(path: Path) -> str:
    if path.suffix == ".jsonl":
        return "transcript"
    if path.suffix in {".md", ".txt"}:
        return "note"
    return "doc"


def iter_files(target: Path):
    if target.is_file():
        if target.suffix.lower() in TEXT_EXTS:
            yield target
        return
    for p in target.rglob("*"):
        if p.is_file() and p.suffix.lower() in TEXT_EXTS:
            yield p


def ingest_file(store, path: Path, extract_mode: str = 'raw') -> bool:
    kind = detect_kind(path)
    try:
        if kind == "transcript":
            return ingest_session_file(store, path, extract_mode=extract_mode)
        text = path.read_text(encoding="utf-8", errors="ignore")
        chunks = chunk_text(text)
    except Exception:
        return False

    if not text.strip():
        return False

    store.upsert_document(str(path), kind, text, chunks=chunks)
    return True


def ingest_path(store, target: Path, extract_mode: str = 'raw') -> int:
    count = 0
    for path in iter_files(target):
        if ingest_file(store, path, extract_mode=extract_mode):
            count += 1
    return count
