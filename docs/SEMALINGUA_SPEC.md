# SemaLingua v0.1 — Spec

> Ultra-compact semantic compression for CORTEX-NANO and OpenClaw agents.

## Goal

Compress verbose context into a small semantic packet that preserves:

1. what changed
2. why it changed
3. what state it moved
4. how it should be interpreted

## Core rule

```
JSON = container
SL   = semantic contract inside the container
```

---

## Packet shape

```
#<id> <area>:<scope> ⚠️<risk>
- <removed-atom>
+ <added-atom>
~ <old>→<new>
state: <path>:<before>→<after>
causal: <source>→<effect>; <source>→<effect>
intent: <goal>
posture: <direction> confidence:<level>
conflict: <scope>:<key>
```

---

## Operators

| Symbol | Meaning |
|--------|---------|
| `#` | Stable anchor / packet id |
| `@` | Actor / entity |
| `-` | Removed semantic atom |
| `+` | Added semantic atom |
| `~` | Modified semantic atom |
| `→` | Causal or state transition |
| `⚠️` | Risk / severity marker |

---

## Atoms

Use short canonical nouns/verbs only.

```
Good: legacy-token, strict-validation, auth, retry-policy
Bad:  "removed some old token code"
```

---

## Merge rules

- Same anchor → update packet
- Same conflict key with opposite deltas → `ERR:CONFLICT`
- Same state path → merges by latest valid transition
- Duplicate semantic deltas → collapse into one

---

## When to use

- PR / issue / change ingestion
- Memory compaction
- Agent-to-agent transport
- Long context reduction
- Semantic dedupe / clustering

## When NOT to use

- Simple metadata only
- Cases where plain JSON fields are enough
- Human prose meant for direct publishing

---

## Example

```
#PR1234 area:auth ⚠️medium
- legacy-token
+ strict-validation
state: auth:v1→v2
causal: legacy-token→bypass-risk; strict-validation→risk↓
intent: harden-auth
posture: security↑ confidence:high
conflict: auth:legacy-token
```

JSON wrapper:

```json
{
  "type": "pr_delta",
  "sl": "#PR1234 area:auth ⚠️medium\n- legacy-token\n+ strict-validation\n..."
}
```

---

## Compression guidance

- Prefer atoms over sentences
- Prefer deltas over descriptions
- Prefer state transitions over summaries
- Keep 1 packet = 1 semantic unit
- Omit fields that add no action value

---

## Litmus test

If JSON only describes, SL should let the agent:

1. **merge** — combine two packets on the same anchor
2. **compare** — detect what changed between versions
3. **detect conflict** — flag opposing deltas on the same key
4. **reconstruct state** — rebuild current state from a chain of packets

---

## Implementation

SemaLingua is implemented in [`src/cortex_nano/semalingua.py`](../src/cortex_nano/semalingua.py).

```python
from cortex_nano.semalingua import compress_atom, compress_session, decompress, parse_sl

# Compress raw text into a SL packet
sl = compress_atom("Rewrote auth to use strict token validation", importance=0.8)

# Decompress back to human-readable summary
result = decompress(sl)
print(result["summary"])

# Parse a SL string into a structured SLPacket
packet = parse_sl(sl)
print(packet.added)   # ['strict', 'token', 'validation', ...]
```

Via API:

```bash
curl -X POST http://127.0.0.1:9743/compress \
  -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/json" \
  -d '{"content": "Rewrote auth to use strict token validation", "importance": 0.8, "decompress": true}'
```
