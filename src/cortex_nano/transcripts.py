from __future__ import annotations

import json
from pathlib import Path


TEXT_TYPES = {'text', 'thinking'}
SKIP_ROLES = {'toolResult'}


def _flatten_content(content):
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = []
        for item in content:
            if not isinstance(item, dict):
                continue
            itype = item.get('type')
            if itype in TEXT_TYPES:
                text = item.get('text') or item.get('thinking') or ''
                if text:
                    parts.append(str(text).strip())
            elif itype == 'toolCall':
                name = item.get('name', 'tool')
                args = item.get('arguments', {})
                parts.append(f"[toolCall:{name}] {json.dumps(args, ensure_ascii=False)[:500]}")
        return '\n'.join(p for p in parts if p).strip()
    return ''


def parse_openclaw_jsonl(path: Path):
    turns = []
    with path.open('r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue

            if not isinstance(obj, dict) or obj.get('type') != 'message':
                continue

            msg = obj.get('message', {})
            if not isinstance(msg, dict):
                continue

            role = msg.get('role')
            if role in SKIP_ROLES or role not in {'user', 'assistant'}:
                continue

            content = _flatten_content(msg.get('content'))
            if not content:
                continue

            turns.append({'role': role, 'content': content})
    return turns


def transcript_to_blocks(turns):
    blocks = []
    cur = []
    for turn in turns:
        cur.append(f"{turn['role'].upper()}: {turn['content']}")
        if len(cur) >= 4:
            blocks.append('\n\n'.join(cur))
            cur = []
    if cur:
        blocks.append('\n\n'.join(cur))
    return blocks
