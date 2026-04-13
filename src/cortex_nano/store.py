from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .search import score

# ── Schema ────────────────────────────────────────────────────────────────────

_SCHEMA_DOCUMENTS = """
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

_SCHEMA_GRAPH = """
create table if not exists atoms (
  id text primary key,
  scope text not null default 'private',
  content_raw text not null,
  content_compressed text,
  importance real not null default 0.5,
  state text not null default 'active',
  source_type text,
  source_ref text,
  tags text default '[]',
  created_at text not null,
  updated_at text not null,
  last_accessed_at text not null
);

create index if not exists idx_atoms_scope_created on atoms(scope, created_at desc);
create index if not exists idx_atoms_importance on atoms(importance desc);

create table if not exists trails (
  id text primary key,
  from_id text not null,
  to_id text not null,
  scope text not null default 'private',
  weight real not null default 0.5,
  weak_floor real not null default 0.1,
  decay_rate real not null default 0.01,
  reinforce_count integer not null default 1,
  link_reason text,
  created_at text not null,
  updated_at text not null,
  last_reinforced_at text not null,
  foreign key(from_id) references atoms(id),
  foreign key(to_id) references atoms(id)
);

create index if not exists idx_trails_from on trails(from_id);
create index if not exists idx_trails_to on trails(to_id);
create unique index if not exists idx_trails_pair on trails(from_id, to_id, scope);

create table if not exists molecules (
  id text primary key,
  scope text not null default 'private',
  label text not null,
  summary text,
  strength real not null default 0.5,
  created_at text not null,
  updated_at text not null
);

create table if not exists cells (
  id text primary key,
  scope text not null default 'private',
  label text not null,
  summary text,
  strength real not null default 0.5,
  created_at text not null,
  updated_at text not null
);

create table if not exists memberships (
  id text primary key,
  parent_type text not null,
  parent_id text not null,
  child_type text not null,
  child_id text not null,
  scope text not null default 'private',
  weight real not null default 0.5,
  created_at text not null,
  updated_at text not null
);

create index if not exists idx_memberships_parent on memberships(parent_type, parent_id);
create index if not exists idx_memberships_child on memberships(child_type, child_id);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _uid() -> str:
    return str(uuid.uuid4())


# ── Store ─────────────────────────────────────────────────────────────────────

class NanoStore:
    def __init__(self, root: Path):
        self.root = root
        self.db_path = self.root / "nano.db"

    def init(self):
        self.root.mkdir(parents=True, exist_ok=True)
        with self._conn() as conn:
            conn.executescript(_SCHEMA_DOCUMENTS)
            conn.executescript(_SCHEMA_GRAPH)

    def _conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("pragma foreign_keys = on")
        conn.execute("pragma journal_mode = wal")
        return conn

    # ── Documents / chunks (ingestion pipeline) ───────────────────────────────

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
        for row in rows:
            s = score(query, row["content"])
            if query.lower() in row["content"].lower():
                s += 0.25
            if row["kind"] == "session_note":
                s += 0.05
            if s > 0:
                ranked.append({"path": row["doc_path"], "kind": row["kind"], "snippet": row["snippet"], "score": s})
        ranked.sort(key=lambda x: (x["score"], x["kind"] == "session_note"), reverse=True)
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
        return [{"path": r["path"], "kind": r["kind"], "snippet": r["snippet"]} for r in rows]

    # ── Atoms ─────────────────────────────────────────────────────────────────

    def create_atom(self, content: str, scope: str = "private", importance: float = 0.5,
                    source_type: str | None = None, source_ref: str | None = None,
                    tags: list | None = None) -> dict:
        import json
        from .semalingua import compress_atom
        now = _now()
        atom_id = _uid()
        compressed = compress_atom(content, atom_id=atom_id, scope=scope,
                                   source_type=source_type, tags=tags, importance=importance)
        with self._conn() as conn:
            conn.execute(
                """insert into atoms(id, scope, content_raw, content_compressed, importance, state,
                   source_type, source_ref, tags, created_at, updated_at, last_accessed_at)
                   values(?,?,?,?,?,?,?,?,?,?,?,?)""",
                (atom_id, scope, content, compressed, importance, "active",
                 source_type, source_ref, json.dumps(tags or []), now, now, now),
            )
        return self.fetch_atom(atom_id)

    def fetch_atom(self, atom_id: str) -> dict | None:
        with self._conn() as conn:
            row = conn.execute("select * from atoms where id = ?", (atom_id,)).fetchone()
        if row is None:
            return None
        # touch last_accessed_at
        with self._conn() as conn:
            conn.execute("update atoms set last_accessed_at = ? where id = ?", (_now(), atom_id))
        return dict(row)

    def list_atoms(self, scope: str = "private", q: str = "", limit: int = 20,
                   state: str = "active") -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                """select * from atoms where scope = ? and state = ?
                   order by importance desc, created_at desc limit ?""",
                (scope, state, limit * 3 if q else limit),
            ).fetchall()
        atoms = [dict(r) for r in rows]
        if q:
            q_lower = q.lower()
            for a in atoms:
                a["_qs"] = score(q, a["content_raw"]) + (0.3 if q_lower in a["content_raw"].lower() else 0)
            atoms = [a for a in atoms if a["_qs"] > 0]
            atoms.sort(key=lambda a: a["_qs"], reverse=True)
            atoms = atoms[:limit]
            for a in atoms:
                del a["_qs"]
        return atoms

    def update_atom_importance(self, atom_id: str, importance: float):
        with self._conn() as conn:
            conn.execute(
                "update atoms set importance = ?, updated_at = ? where id = ?",
                (max(0.0, min(1.0, importance)), _now(), atom_id),
            )

    def delete_atom(self, atom_id: str):
        with self._conn() as conn:
            conn.execute("update atoms set state = 'deleted', updated_at = ? where id = ?", (_now(), atom_id))

    def atom_stats(self) -> dict:
        with self._conn() as conn:
            atoms = conn.execute("select count(*) from atoms where state = 'active'").fetchone()[0]
            trails = conn.execute("select count(*) from trails").fetchone()[0]
            molecules = conn.execute("select count(*) from molecules").fetchone()[0]
            cells = conn.execute("select count(*) from cells").fetchone()[0]
            docs = conn.execute("select count(*) from documents").fetchone()[0]
            chunks = conn.execute("select count(*) from chunks").fetchone()[0]
        return {"atoms": atoms, "trails": trails, "molecules": molecules,
                "cells": cells, "documents": docs, "chunks": chunks}

    # ── Trails ────────────────────────────────────────────────────────────────

    def create_or_reinforce_trail(self, from_id: str, to_id: str, scope: str = "private",
                                  weight: float = 0.5, link_reason: str | None = None) -> dict:
        now = _now()
        with self._conn() as conn:
            existing = conn.execute(
                "select * from trails where from_id = ? and to_id = ? and scope = ?",
                (from_id, to_id, scope),
            ).fetchone()
            if existing:
                new_weight = min(1.0, existing["weight"] + 0.1)
                new_count = existing["reinforce_count"] + 1
                conn.execute(
                    """update trails set weight = ?, reinforce_count = ?,
                       last_reinforced_at = ?, updated_at = ? where id = ?""",
                    (new_weight, new_count, now, now, existing["id"]),
                )
                trail_id = existing["id"]
            else:
                trail_id = _uid()
                conn.execute(
                    """insert into trails(id, from_id, to_id, scope, weight, link_reason,
                       created_at, updated_at, last_reinforced_at)
                       values(?,?,?,?,?,?,?,?,?)""",
                    (trail_id, from_id, to_id, scope, weight, link_reason, now, now, now),
                )
        return self.fetch_trail(trail_id)

    def fetch_trail(self, trail_id: str) -> dict | None:
        with self._conn() as conn:
            row = conn.execute("select * from trails where id = ?", (trail_id,)).fetchone()
        return dict(row) if row else None

    def list_trails_for_atom(self, atom_id: str, scope: str = "private") -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "select * from trails where (from_id = ? or to_id = ?) and scope = ? order by weight desc",
                (atom_id, atom_id, scope),
            ).fetchall()
        return [dict(r) for r in rows]

    def decay_trails(self, scope: str = "private") -> dict:
        with self._conn() as conn:
            trails = conn.execute(
                "select id, weight, weak_floor, decay_rate from trails where scope = ?", (scope,)
            ).fetchall()
            decayed = dissolved = 0
            now = _now()
            for t in trails:
                new_w = max(t["weak_floor"], t["weight"] - t["decay_rate"])
                if new_w != t["weight"]:
                    conn.execute("update trails set weight = ?, updated_at = ? where id = ?",
                                 (new_w, now, t["id"]))
                    decayed += 1
                    if new_w <= t["weak_floor"]:
                        dissolved += 1
        return {"decayed": decayed, "at_floor": dissolved}

    # ── Molecules ─────────────────────────────────────────────────────────────

    def create_or_update_molecule(self, label: str, scope: str = "private",
                                  summary: str | None = None, strength: float = 0.5,
                                  molecule_id: str | None = None) -> dict:
        now = _now()
        mol_id = molecule_id or _uid()
        with self._conn() as conn:
            existing = conn.execute("select id from molecules where id = ?", (mol_id,)).fetchone()
            if existing:
                conn.execute(
                    "update molecules set label=?, summary=?, strength=?, updated_at=? where id=?",
                    (label, summary, strength, now, mol_id),
                )
            else:
                conn.execute(
                    "insert into molecules(id, scope, label, summary, strength, created_at, updated_at) values(?,?,?,?,?,?,?)",
                    (mol_id, scope, label, summary, strength, now, now),
                )
            row = conn.execute("select * from molecules where id = ?", (mol_id,)).fetchone()
        return dict(row)

    def upsert_membership(self, parent_type: str, parent_id: str,
                          child_type: str, child_id: str,
                          scope: str = "private", weight: float = 0.5):
        now = _now()
        mem_id = f"{parent_type}:{parent_id}:{child_type}:{child_id}"
        with self._conn() as conn:
            conn.execute(
                """insert into memberships(id, parent_type, parent_id, child_type, child_id, scope, weight, created_at, updated_at)
                   values(?,?,?,?,?,?,?,?,?)
                   on conflict(id) do update set weight=excluded.weight, updated_at=excluded.updated_at""",
                (mem_id, parent_type, parent_id, child_type, child_id, scope, weight, now, now),
            )

    # ── Molecule auto-formation ───────────────────────────────────────────────

    def form_molecules(self, scope: str = "private", min_trail_weight: float = 0.6,
                       min_reinforce_count: int = 2, limit: int = 100) -> dict:
        """
        Find connected clusters of atoms linked by strong trails and
        create/update molecules from them. Ported from _src_v1 nano_form_molecules().
        """
        with self._conn() as conn:
            rows = conn.execute(
                """select from_id, to_id, weight from trails
                   where scope = ? and weight >= ? and reinforce_count >= ?
                   order by weight desc, reinforce_count desc limit ?""",
                (scope, min_trail_weight, min_reinforce_count, limit),
            ).fetchall()

        # Build adjacency graph
        graph: dict[str, list[str]] = {}
        edge_weights: dict[str, float] = {}
        for r in rows:
            a, b, w = r["from_id"], r["to_id"], float(r["weight"])
            graph.setdefault(a, []).append(b)
            graph.setdefault(b, []).append(a)
            edge_weights[f"{a}|{b}"] = w
            edge_weights[f"{b}|{a}"] = w

        # BFS connected components
        visited: set[str] = set()
        clusters: list[list[str]] = []
        for atom_id in graph:
            if atom_id in visited:
                continue
            queue = [atom_id]
            cluster: list[str] = []
            while queue:
                current = queue.pop(0)
                if current in visited:
                    continue
                visited.add(current)
                cluster.append(current)
                queue.extend(n for n in graph.get(current, []) if n not in visited)
            if len(cluster) >= 2:
                clusters.append(sorted(cluster))

        # Create/update molecules from clusters
        created = []
        for cluster in clusters:
            # Average edge weight as molecule strength
            edge_ws = []
            for i in range(len(cluster)):
                for j in range(i + 1, len(cluster)):
                    k = f"{cluster[i]}|{cluster[j]}"
                    if k in edge_weights:
                        edge_ws.append(edge_weights[k])
            strength = min(1.0, sum(edge_ws) / len(edge_ws)) if edge_ws else 0.5

            # Summary from first 4 atom contents
            snippets = []
            for aid in cluster[:4]:
                atom = self.fetch_atom(aid)
                if atom:
                    snippets.append(atom["content_raw"][:80].replace("\n", " "))
            summary = " | ".join(snippets)
            label = summary[:60] or f"molecule-{cluster[0][:8]}"

            mol = self.create_or_update_molecule(
                label=label, scope=scope, summary=summary, strength=strength
            )
            for aid in cluster:
                w = edge_weights.get(f"{cluster[0]}|{aid}", strength)
                self.upsert_membership("molecule", mol["id"], "atom", aid, scope=scope, weight=w)
            created.append(mol)

        pruned = self._prune_subsumed_molecules(scope)
        return {
            "scope": scope,
            "source_trails": len(rows),
            "clusters": len(clusters),
            "molecules_created": len(created),
            "pruned": len(pruned),
        }

    def _prune_subsumed_molecules(self, scope: str) -> list[dict]:
        """Remove molecules whose atom sets are fully contained in a larger molecule."""
        with self._conn() as conn:
            mols = conn.execute(
                "select id, strength from molecules where scope = ? order by strength desc",
                (scope,),
            ).fetchall()
            mol_atoms: dict[str, list[str]] = {}
            for m in mols:
                rows = conn.execute(
                    "select child_id from memberships where parent_type='molecule' and parent_id=? and child_type='atom' order by child_id",
                    (m["id"],),
                ).fetchall()
                mol_atoms[m["id"]] = [r["child_id"] for r in rows]

        removed = []
        mol_ids = [m["id"] for m in mols]
        for cand_id in mol_ids:
            cand_atoms = mol_atoms.get(cand_id, [])
            if len(cand_atoms) < 2:
                continue
            cand_set = set(cand_atoms)
            for cont_id in mol_ids:
                if cont_id == cand_id:
                    continue
                cont_atoms = set(mol_atoms.get(cont_id, []))
                if len(cont_atoms) > len(cand_set) and cand_set.issubset(cont_atoms):
                    with self._conn() as conn:
                        conn.execute("delete from memberships where parent_type='molecule' and parent_id=?", (cand_id,))
                        conn.execute("delete from memberships where child_type='molecule' and child_id=?", (cand_id,))
                        conn.execute("delete from molecules where id=?", (cand_id,))
                    removed.append({"molecule_id": cand_id, "subsumed_by": cont_id})
                    mol_atoms.pop(cand_id, None)
                    break
        return removed

    # ── Cell auto-formation ───────────────────────────────────────────────────

    def form_cells(self, scope: str = "private", min_molecule_strength: float = 0.55,
                   limit: int = 100) -> dict:
        """
        Group overlapping molecules into cells. Ported from _src_v1 nano_form_cells().
        """
        with self._conn() as conn:
            mols = conn.execute(
                "select * from molecules where scope = ? and strength >= ? order by strength desc limit ?",
                (scope, min_molecule_strength, limit),
            ).fetchall()
            mol_atoms: dict[str, list[str]] = {}
            for m in mols:
                rows = conn.execute(
                    "select child_id from memberships where parent_type='molecule' and parent_id=? and child_type='atom' order by child_id",
                    (m["id"],),
                ).fetchall()
                mol_atoms[m["id"]] = [r["child_id"] for r in rows]

        # Group molecules by shared atoms or summary terms
        import re as _re
        groups: list[dict] = []
        for mol in mols:
            mol = dict(mol)
            atom_ids = mol_atoms.get(mol["id"], [])
            if len(atom_ids) < 2:
                continue
            mol_terms = set(_re.split(r"[^a-z0-9]+", (mol.get("summary") or "").lower())) - {""}

            merged = False
            for group in groups:
                shared_atoms = set(group["atom_ids"]) & set(atom_ids)
                shared_terms = mol_terms & group["terms"]
                if shared_atoms or len(shared_terms) >= 2:
                    group["molecules"].append(mol)
                    group["atom_ids"] = list(set(group["atom_ids"]) | set(atom_ids))
                    group["terms"] |= mol_terms
                    group["summary"] = (group["summary"] + " " + (mol.get("summary") or "")).strip()
                    merged = True
                    break
            if not merged:
                groups.append({
                    "molecules": [mol],
                    "atom_ids": atom_ids,
                    "terms": mol_terms,
                    "summary": mol.get("summary") or "",
                })

        created = []
        for group in groups:
            if len(group["molecules"]) < 2:
                continue
            mol_list = group["molecules"]
            strength = min(1.0, sum(float(m["strength"]) for m in mol_list) / len(mol_list))
            summaries = [m.get("summary") or m.get("label") or "" for m in mol_list[:3]]
            summary = " | ".join(s[:80] for s in summaries if s)
            label = summary[:60] or f"cell-{mol_list[0]['id'][:8]}"

            cell = self.create_or_update_cell(
                label=label, scope=scope, summary=summary, strength=strength
            )
            for mol in mol_list:
                self.upsert_membership("cell", cell["id"], "molecule", mol["id"], scope=scope, weight=float(mol["strength"]))
            created.append(cell)

        return {
            "scope": scope,
            "source_molecules": len(mols),
            "cells_created": len(created),
        }

    def create_or_update_cell(self, label: str, scope: str = "private",
                              summary: str | None = None, strength: float = 0.5,
                              cell_id: str | None = None) -> dict:
        now = _now()
        cid = cell_id or _uid()
        with self._conn() as conn:
            existing = conn.execute("select id from cells where id = ?", (cid,)).fetchone()
            if existing:
                conn.execute(
                    "update cells set label=?, summary=?, strength=?, updated_at=? where id=?",
                    (label, summary, strength, now, cid),
                )
            else:
                conn.execute(
                    "insert into cells(id, scope, label, summary, strength, created_at, updated_at) values(?,?,?,?,?,?,?)",
                    (cid, scope, label, summary, strength, now, now),
                )
            row = conn.execute("select * from cells where id = ?", (cid,)).fetchone()
        return dict(row)

    # ── Dissolve weak structures ───────────────────────────────────────────────

    def dissolve_weak_structures(self, scope: str = "private",
                                 min_molecule_strength: float = 0.2,
                                 min_cell_strength: float = 0.2) -> dict:
        """
        Delete molecules and cells below strength threshold, plus their memberships.
        Atoms are never deleted. Ported from _src_v1 nano_dissolve_weak_structures().
        """
        removed_memberships = removed_molecules = removed_cells = 0
        with self._conn() as conn:
            weak_mols = [r["id"] for r in conn.execute(
                "select id from molecules where scope = ? and strength < ?",
                (scope, min_molecule_strength),
            ).fetchall()]
            for mid in weak_mols:
                c1 = conn.execute("delete from memberships where parent_type='molecule' and parent_id=?", (mid,)).rowcount
                c2 = conn.execute("delete from memberships where child_type='molecule' and child_id=?", (mid,)).rowcount
                conn.execute("delete from molecules where id=?", (mid,))
                removed_memberships += c1 + c2
                removed_molecules += 1

            weak_cells = [r["id"] for r in conn.execute(
                "select id from cells where scope = ? and strength < ?",
                (scope, min_cell_strength),
            ).fetchall()]
            for cid in weak_cells:
                c1 = conn.execute("delete from memberships where parent_type='cell' and parent_id=?", (cid,)).rowcount
                conn.execute("delete from cells where id=?", (cid,))
                removed_memberships += c1
                removed_cells += 1

        return {
            "removed_molecules": removed_molecules,
            "removed_cells": removed_cells,
            "removed_memberships": removed_memberships,
        }
