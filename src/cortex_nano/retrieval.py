"""
Structural retrieval — ported from _src_v1/bootstrap/bootstrap.php::nano_structural_retrieve().

Scoring model:
  text_match   0.40  — cosine similarity of query vs atom content
  importance   0.30  — atom.importance weight
  trail        0.00–1.0 — sum of incoming trail weights from seed atom
  molecule     0.00–0.45 — membership boost from shared molecule
  cell         0.00–0.25 — membership boost from shared cell
  recency      0.00–0.30 — decays over 24 h since last_accessed_at
"""

from __future__ import annotations

from datetime import datetime, timezone

from .search import score as text_score
from .store import NanoStore


def _age_hours(ts: str) -> float:
    try:
        dt = datetime.fromisoformat(ts)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        delta = datetime.now(timezone.utc) - dt
        return delta.total_seconds() / 3600
    except Exception:
        return 0.0


def structural_retrieve(store: NanoStore, query: str = "", seed_atom_id: str = "",
                        scope: str = "private", limit: int = 10) -> list[dict]:
    if not query and not seed_atom_id:
        raise ValueError("query or seed_atom_id required")

    candidates: dict[str, dict] = {}  # atom_id -> {atom, scores}

    def _ensure(atom: dict):
        aid = atom["id"]
        if aid not in candidates:
            candidates[aid] = {
                "atom": atom,
                "scores": {"text_match": 0.0, "importance": float(atom["importance"]) * 0.3,
                           "trail": 0.0, "molecule": 0.0, "cell": 0.0, "recency": 0.0},
            }
        return candidates[aid]

    # ── Text-match seed atoms ──────────────────────────────────────────────────

    if query:
        for atom in store.list_atoms(scope=scope, q=query, limit=limit * 3):
            c = _ensure(atom)
            c["scores"]["text_match"] = 0.4 * min(1.0, text_score(query, atom["content_raw"]) * 2 + (
                0.3 if query.lower() in atom["content_raw"].lower() else 0))

    # ── Seed atom neighborhood ─────────────────────────────────────────────────

    if seed_atom_id:
        seed = store.fetch_atom(seed_atom_id)
        if seed:
            c = _ensure(seed)
            c["scores"]["trail"] = 1.0

            # Direct trail neighbors
            for trail in store.list_trails_for_atom(seed_atom_id, scope=scope):
                neighbor_id = trail["to_id"] if trail["from_id"] == seed_atom_id else trail["from_id"]
                neighbor = store.fetch_atom(neighbor_id)
                if neighbor:
                    nc = _ensure(neighbor)
                    nc["scores"]["trail"] = min(1.0, nc["scores"]["trail"] + float(trail["weight"]))

            # Molecule co-membership boost
            with store._conn() as conn:
                mol_rows = conn.execute(
                    """select parent_id, weight from memberships
                       where child_type='atom' and child_id=? and parent_type='molecule' and scope=?""",
                    (seed_atom_id, scope),
                ).fetchall()
                seed_molecule_ids = {r["parent_id"]: float(r["weight"]) for r in mol_rows}

                for mol_id, mol_w in seed_molecule_ids.items():
                    member_atoms = conn.execute(
                        "select child_id, weight from memberships where parent_type='molecule' and parent_id=? and child_type='atom'",
                        (mol_id,),
                    ).fetchall()
                    mol_size = max(1, len(member_atoms))
                    for ma in member_atoms:
                        neighbor = store.fetch_atom(ma["child_id"])
                        if not neighbor:
                            continue
                        nc = _ensure(neighbor)
                        boost = ((mol_w * 0.35) + (float(ma["weight"]) * 0.15)) / mol_size
                        if ma["child_id"] == seed_atom_id:
                            boost *= 0.35
                        nc["scores"]["molecule"] = max(nc["scores"]["molecule"], min(0.45, boost))

                # Cell co-membership boost
                cell_ids: dict[str, float] = {}
                for mol_id in seed_molecule_ids:
                    cell_rows = conn.execute(
                        """select parent_id, weight from memberships
                           where parent_type='cell' and child_type='molecule' and child_id=? and scope=?""",
                        (mol_id, scope),
                    ).fetchall()
                    for cr in cell_rows:
                        cell_ids[cr["parent_id"]] = max(cell_ids.get(cr["parent_id"], 0.0), float(cr["weight"]))

                for cell_id, cell_w in cell_ids.items():
                    cell_mols = conn.execute(
                        "select child_id, weight from memberships where parent_type='cell' and parent_id=? and child_type='molecule'",
                        (cell_id,),
                    ).fetchall()
                    n_mols = max(1, len(cell_mols))
                    for cm in cell_mols:
                        cell_atoms = conn.execute(
                            "select child_id, weight from memberships where parent_type='molecule' and parent_id=? and child_type='atom'",
                            (cm["child_id"],),
                        ).fetchall()
                        n_atoms = max(1, len(cell_atoms))
                        for ca in cell_atoms:
                            neighbor = store.fetch_atom(ca["child_id"])
                            if not neighbor:
                                continue
                            nc = _ensure(neighbor)
                            is_seed_mol = cm["child_id"] in seed_molecule_ids
                            boost = (cell_w * 0.2 + float(cm["weight"]) * 0.1 + float(ca["weight"]) * 0.08) / max(1, n_mols * n_atoms)
                            if is_seed_mol and ca["child_id"] == seed_atom_id:
                                boost *= 0.2
                            nc["scores"]["cell"] = max(nc["scores"]["cell"], min(0.25, boost))

    # ── Recency + final score ──────────────────────────────────────────────────

    results = []
    for c in candidates.values():
        age_h = _age_hours(c["atom"].get("last_accessed_at", ""))
        c["scores"]["recency"] = max(0.0, 0.3 - min(0.3, age_h / 24 * 0.3))
        total = sum(c["scores"].values())
        results.append({
            "atom": c["atom"],
            "score": round(total, 4),
            "scores": c["scores"],
            "retrieval_mode": "structural",
        })

    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:limit]


def build_context_bundle(store: NanoStore, query: str = "", seed_atom_id: str = "",
                         scope: str = "private", limit: int = 8,
                         compressed: bool = False) -> str:
    """
    Build a compact context string ready to inject into an LLM prompt.

    compressed=True  → use SemaLingua content_compressed field (smaller)
    compressed=False → use content_raw (full fidelity)
    """
    results = structural_retrieve(store, query=query, seed_atom_id=seed_atom_id,
                                  scope=scope, limit=limit)
    if not results:
        return "[CORTEX-NANO] no relevant memory found"

    header = f"[CORTEX-NANO MEMORY] query={repr(query)} scope={scope} atoms={len(results)}"
    lines = [header, ""]

    for r in results:
        atom = r["atom"]
        aid = atom["id"][:8]
        imp = float(atom.get("importance", 0.5))
        score = r["score"]

        # trail context
        trails = store.list_trails_for_atom(atom["id"], scope=scope)
        trail_refs = ""
        if trails:
            linked = [t["to_id"][:8] if t["from_id"] == atom["id"] else t["from_id"][:8]
                      for t in trails[:3]]
            trail_refs = f"  linked→ {', '.join(linked)}"

        content = (atom.get("content_compressed") or atom.get("content_raw", "")) \
            if compressed else atom.get("content_raw", "")

        lines.append(f"[{aid}] score={score:.3f} importance={imp:.1f}{trail_refs}")
        lines.append(content.strip()[:400])
        lines.append("")

    return "\n".join(lines).rstrip()
