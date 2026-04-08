from __future__ import annotations

from collections import Counter
import math
import re

WORD_RE = re.compile(r"[a-zA-Z0-9_]{2,}")


def tokenize(text: str):
    return [w.lower() for w in WORD_RE.findall(text)]


def score(query: str, text: str):
    q = tokenize(query)
    t = tokenize(text)
    if not q or not t:
        return 0.0
    qc = Counter(q)
    tc = Counter(t)
    dot = sum(qc[w] * tc.get(w, 0) for w in qc)
    qn = math.sqrt(sum(v * v for v in qc.values()))
    tn = math.sqrt(sum(v * v for v in tc.values()))
    if qn == 0 or tn == 0:
        return 0.0
    return dot / (qn * tn)
