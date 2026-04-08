import sqlite3
from pathlib import Path

from .search import score


SCHEMA = """
create table if not exists documents (
  id integer primary key,
  path text unique not null,
  kind text not null,
  content text not null,
  snippet text not null,
  created_at datetime default current_timestamp
);

create table if not exists chunks (
  id integer primary key,
  doc_path text not null,
  chunk_index integer not null,
  kind text not null,
  content text not null,
  snippet text not null,
  unique(doc_path, chunk_index)
);
"""


class NanoStore:
    def __init__(self, root: Path):
        self.root = root
        self.db_path = self.root / "nano.db"

    def init(self):
        self.root.mkdir(parents=True, exist_ok=True)
        with self._conn() as conn:
            conn.executescript(SCHEMA)

    def _conn(self):
        return sqlite3.connect(self.db_path)

    def upsert_document(self, path: str, kind: str, content: str, chunks=None):
        snippet = " ".join(content.strip().split())[:220]
        chunks = chunks or [content]
        with self._conn() as conn:
            conn.execute(
                "insert into documents(path, kind, content, snippet) values(?,?,?,?) "
                "on conflict(path) do update set kind=excluded.kind, content=excluded.content, snippet=excluded.snippet",
                (path, kind, content, snippet),
            )
            conn.execute("delete from chunks where doc_path = ?", (path,))
            for idx, chunk in enumerate(chunks):
                csnip = " ".join(chunk.strip().split())[:220]
                conn.execute(
                    "insert into chunks(doc_path, chunk_index, kind, content, snippet) values(?,?,?,?,?)",
                    (path, idx, kind, chunk, csnip),
                )

    def search(self, query: str, limit: int = 5):
        with self._conn() as conn:
            rows = conn.execute(
                "select doc_path, kind, snippet, content from chunks"
            ).fetchall()
        ranked = []
        for path, kind, snippet, content in rows:
            s = score(query, content)
            if query.lower() in content.lower():
                s += 0.25
            if kind == 'session_note':
                s += 0.05
            if s > 0:
                ranked.append({"path": path, "kind": kind, "snippet": snippet, "score": s})
        ranked.sort(key=lambda x: (x["score"], x["kind"] == 'session_note'), reverse=True)
        return ranked[:limit]

    def sync_preview(self, limit: int = 10, kind: str | None = None):
        with self._conn() as conn:
            if kind:
                rows = conn.execute(
                    "select path, kind, snippet from documents where kind = ? order by id desc limit ?",
                    (kind, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "select path, kind, snippet from documents order by id desc limit ?",
                    (limit,),
                ).fetchall()
        return [{"path": r[0], "kind": r[1], "snippet": r[2]} for r in rows]
