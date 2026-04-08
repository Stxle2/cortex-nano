from __future__ import annotations


def render_session_semalingua(path: str, notes: dict):
    lines = [f"session: {path}"]
    if notes.get('mode'):
        lines.append(f"extract_mode: {notes['mode']}")
    if notes.get('decisions'):
        lines.append("decisions: " + " | ".join(notes['decisions']))
    if notes.get('actions'):
        lines.append("actions: " + " | ".join(notes['actions']))
    if notes.get('preferences'):
        lines.append("prefs: " + " | ".join(notes['preferences']))
    if notes.get('quotes'):
        lines.append("quotes: " + " | ".join(notes['quotes']))
    return "\n".join(lines)
