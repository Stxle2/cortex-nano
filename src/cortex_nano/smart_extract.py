from __future__ import annotations


def extract_session_notes_smart(turns):
    # Placeholder smart mode.
    # Real NVIDIA-backed extraction gets wired next; keep interface stable now.
    decisions = []
    actions = []
    preferences = []
    quotes = []

    for t in turns[:12]:
        content = " ".join(t.get('content', '').strip().split())
        if not content:
            continue
        if len(content) > 50 and len(quotes) < 4:
            quotes.append(f"{t.get('role','user')}: {content[:240]}")

    if turns:
        first_user = next((t.get('content', '') for t in turns if t.get('role') == 'user' and t.get('content')), '')
        if first_user:
            actions.append(first_user[:220])

    return {
        'decisions': decisions,
        'actions': actions,
        'preferences': preferences,
        'quotes': quotes,
        'mode': 'smart',
    }
