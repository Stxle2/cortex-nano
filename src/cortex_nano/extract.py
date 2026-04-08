from __future__ import annotations

import re

DECISION_RE = re.compile(r"\b(decide[sd]?|decision|we should|we will|go with|switch to|use )\b", re.I)
ACTION_RE = re.compile(r"\b(todo|next|follow up|need to|should do|start|build|implement|fix)\b", re.I)
PREF_RE = re.compile(r"\b(prefer|likes?|dislikes?|wants?|doesn't want|avoid)\b", re.I)


def extract_session_notes(turns):
    decisions = []
    actions = []
    prefs = []
    quotes = []

    for t in turns:
        content = " ".join(t.get('content', '').strip().split())
        if not content:
            continue
        if DECISION_RE.search(content):
            decisions.append(content)
        if ACTION_RE.search(content):
            actions.append(content)
        if PREF_RE.search(content):
            prefs.append(content)
        if len(quotes) < 3 and len(content) > 40:
            quotes.append(f"{t.get('role','user')}: {content[:220]}")

    return {
        'decisions': dedupe(decisions)[:5],
        'actions': dedupe(actions)[:5],
        'preferences': dedupe(prefs)[:5],
        'quotes': dedupe(quotes)[:3],
    }


def dedupe(items):
    out = []
    seen = set()
    for item in items:
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out
