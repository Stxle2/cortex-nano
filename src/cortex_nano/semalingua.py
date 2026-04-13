"""
SemaLingua v0.1 — semantic compression for Cortex Nano.

Spec: ultra-compact packets that preserve what changed, why, what state moved,
and how to interpret it. Zero prose — atoms + operators only.

Packet shape:
  #<id> <area>:<scope> ⚠️<level>
  - <removed-atom>
  + <added-atom>
  ~ <old>→<new>
  state: <path>:<before>→<after>
  causal: <source>→<effect>; ...
  intent: <goal>
  posture: <direction> confidence:<level>
  conflict: <scope>:<key>          (optional)

Operators:
  #   stable anchor / packet id
  @   actor / entity
  -   removed semantic atom
  +   added semantic atom
  ~   modified semantic atom
  →   causal or state transition
  ⚠️  risk / severity marker
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field


# ── Data model ────────────────────────────────────────────────────────────────

@dataclass
class SLPacket:
    id: str = ""
    area: str = "memory"
    scope: str = "private"
    risk: str = "low"
    removed: list[str] = field(default_factory=list)
    added: list[str] = field(default_factory=list)
    modified: list[tuple[str, str]] = field(default_factory=list)
    state: list[str] = field(default_factory=list)
    causal: list[str] = field(default_factory=list)
    intent: str = ""
    posture: str = ""
    conflict: str = ""

    def to_sl(self) -> str:
        risk_emoji = {"medium": "⚠️", "high": "⚠️⚠️"}.get(self.risk, "")
        header = f"#{self.id} {self.area}:{self.scope}"
        if risk_emoji:
            header += f" {risk_emoji}{self.risk}"
        lines = [header]
        for r in self.removed:
            lines.append(f"- {r}")
        for a in self.added:
            lines.append(f"+ {a}")
        for old, new in self.modified:
            lines.append(f"~ {old}→{new}")
        for s in self.state:
            lines.append(f"state: {s}")
        if self.causal:
            lines.append("causal: " + "; ".join(self.causal))
        if self.intent:
            lines.append(f"intent: {self.intent}")
        if self.posture:
            lines.append(f"posture: {self.posture}")
        if self.conflict:
            lines.append(f"conflict: {self.conflict}")
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "id": self.id, "area": self.area, "scope": self.scope, "risk": self.risk,
            "removed": self.removed, "added": self.added,
            "modified": [{"old": o, "new": n} for o, n in self.modified],
            "state": self.state, "causal": self.causal,
            "intent": self.intent, "posture": self.posture, "conflict": self.conflict,
        }


# ── Parser ────────────────────────────────────────────────────────────────────

def parse_sl(sl: str) -> SLPacket:
    """Parse a SemaLingua string into a SLPacket."""
    p = SLPacket()
    for line in sl.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("#"):
            parts = line[1:].split()
            p.id = parts[0] if parts else str(uuid.uuid4())[:8]
            if len(parts) > 1 and ":" in parts[1]:
                p.area, p.scope = parts[1].split(":", 1)
            if len(parts) > 2:
                risk_raw = re.sub(r"[⚠️\s]", "", parts[2])
                p.risk = risk_raw if risk_raw in ("low", "medium", "high") else "low"
            continue
        if line.startswith("- "):
            p.removed.append(line[2:].strip())
        elif line.startswith("+ "):
            p.added.append(line[2:].strip())
        elif line.startswith("~ "):
            body = line[2:].strip()
            if "→" in body:
                old, new = body.split("→", 1)
                p.modified.append((old.strip(), new.strip()))
            else:
                p.modified.append((body, ""))
        elif line.startswith("state:"):
            p.state.append(line[6:].strip())
        elif line.startswith("causal:"):
            for part in line[7:].split(";"):
                c = part.strip()
                if c:
                    p.causal.append(c)
        elif line.startswith("intent:"):
            p.intent = line[7:].strip()
        elif line.startswith("posture:"):
            p.posture = line[8:].strip()
        elif line.startswith("conflict:"):
            p.conflict = line[9:].strip()
    if not p.id:
        p.id = str(uuid.uuid4())[:8]
    return p


# ── Compressor ────────────────────────────────────────────────────────────────

_STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "is", "are", "was", "were",
    "be", "been", "being", "have", "has", "had", "do", "does", "did",
    "will", "would", "could", "should", "may", "might", "shall", "can",
    "to", "of", "in", "on", "at", "by", "for", "with", "from", "into",
    "this", "that", "it", "its", "i", "we", "you", "he", "she", "they",
    "not", "no", "so", "if", "as", "up", "out", "about", "then", "than",
}

_WORD_RE = re.compile(r"[a-zA-Z0-9_\-]{3,}")
_VERB_RE = re.compile(
    r"\b(add|remov|updat|creat|delet|fix|chang|build|deploy|configur|"
    r"migrat|refactor|test|send|receiv|store|retriev|compress|ingest)\w*"
)


def _extract_atoms(text: str, max_atoms: int = 6) -> list[str]:
    """Pull canonical short nouns/verbs — the SL semantic atoms."""
    words = _WORD_RE.findall(text.lower())
    freq: dict[str, int] = {}
    for w in words:
        if w not in _STOPWORDS:
            freq[w] = freq.get(w, 0) + 1
    ranked = sorted(freq.items(), key=lambda x: (-x[1], len(x[0])))
    atoms: list[str] = []
    for word, _ in ranked[:max_atoms * 2]:
        canonical = word.rstrip("s") if len(word) > 4 and word.endswith("s") else word
        if canonical not in atoms:
            atoms.append(canonical)
        if len(atoms) >= max_atoms:
            break
    return atoms


def _extract_intent(text: str) -> str:
    sentences = re.split(r"[.!?\n]", text.strip())
    first = sentences[0].lower().strip() if sentences else ""
    verbs = _VERB_RE.findall(first)
    if verbs:
        atoms = _extract_atoms(first, max_atoms=3)
        return "-".join([verbs[0]] + [a for a in atoms if a != verbs[0]][:2])
    atoms = _extract_atoms(text, max_atoms=2)
    return "-".join(atoms) if atoms else "store"


def _to_atom(text: str) -> str:
    atoms = _extract_atoms(text, max_atoms=3)
    return "-".join(atoms) if atoms else text[:30].replace(" ", "-").lower()


def compress_atom(content: str, atom_id: str = "", scope: str = "private",
                  source_type: str | None = None, tags: list | None = None,
                  importance: float = 0.5) -> str:
    """
    Compress raw atom content into a SemaLingua packet.
    Stored as content_compressed alongside content_raw.
    """
    short_id = atom_id[:8] if atom_id else str(uuid.uuid4())[:8]
    atoms = _extract_atoms(content)
    risk = "high" if importance >= 0.8 else "medium" if importance >= 0.5 else "low"

    p = SLPacket(
        id=short_id,
        area=source_type or "memory",
        scope=scope,
        risk=risk,
        added=atoms,
        intent=_extract_intent(content),
        posture=f"importance:{importance:.1f}",
    )
    if tags:
        p.state.append("tags:" + ",".join(tags))
    return p.to_sl()


def compress_session(path: str, notes: dict, mode: str = "raw") -> str:
    """Compress session extracted notes into a SemaLingua packet."""
    p = SLPacket(
        id=str(uuid.uuid4())[:8],
        area="session",
        scope="private",
        risk="low",
        intent=f"session-{mode}",
        state=[f"source:{path.split('/')[-1]}"],
    )
    for d in (notes.get("decisions") or [])[:4]:
        p.added.append(_to_atom(d))
    for a in (notes.get("actions") or [])[:4]:
        p.causal.append(_to_atom(a) + "→enacted")
    for pref in (notes.get("preferences") or [])[:3]:
        p.state.append("pref:" + _to_atom(pref))
    return p.to_sl()


# ── Decompressor ──────────────────────────────────────────────────────────────

def decompress(sl: str) -> dict:
    """Reconstruct a human-readable summary from a SL packet. Meaning-preserving, not lossless."""
    p = parse_sl(sl)
    lines = []
    if p.added:
        lines.append("Added: " + ", ".join(p.added))
    if p.removed:
        lines.append("Removed: " + ", ".join(p.removed))
    if p.modified:
        lines.append("Changed: " + "; ".join(f"{o} → {n}" for o, n in p.modified))
    if p.state:
        lines.append("State: " + " | ".join(p.state))
    if p.causal:
        lines.append("Causal: " + "; ".join(p.causal))
    if p.intent:
        lines.append("Intent: " + p.intent)
    return {"summary": "\n".join(lines), "packet": p.to_dict()}


# ── Backward compat ───────────────────────────────────────────────────────────

def render_session_semalingua(path: str, notes: dict) -> str:
    return compress_session(path, notes)
