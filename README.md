# CORTEX-NANO

**Local-first memory engine for AI agents.**  
Turns stateless LLMs into stateful systems — stores knowledge as atoms, links them through weighted trails, organizes them into molecules and cells, and retrieves them structurally or semantically.

> *raw information may stay, but structure must be allowed to change.*

---

## What it is

CORTEX-NANO is not a vector store wrapper. It is a local adaptive memory core.

- Runs fully on-device — no cloud, no external dependencies
- Works with any LLM (local or hosted)
- Memory evolves over time instead of sitting as flat storage
- Lightweight enough for local agents, VMs, and embedded use cases
- Part of the broader [OpenClaw](https://github.com/Stxle2) agent ecosystem

---

## Install

```bash
pip install cortex-nano
```

Or from source:

```bash
git clone https://github.com/Stxle2/cortex-nano
cd cortex-nano
pip install -e .
```

---

## Quick start

```bash
# Initialize local memory store
cortex-nano init

# Ingest a file or folder (transcripts, markdown, docs)
cortex-nano ingest ./my-notes

# Search memory
cortex-nano search "authentication refactor"

# Start the local API (for agents)
cortex-nano serve --port 9743
```

---

## Memory model

```
Atom       smallest meaningful unit — raw content + importance + source
 │
Trail      weighted link between atoms — strengthens on reuse, decays on disuse
 │
Molecule   cluster of atoms that appear together repeatedly
 │
Cell       higher-order topic hub formed from related molecules
```

**Atoms** are never deleted — only structure changes.  
**Trails** have a `weak_floor` so they persist at low weight rather than vanish.  
**Decay** is configurable and runs on demand via `POST /decay`.

---

## Local API

Start the server:

```bash
cortex-nano serve --port 9743
export KEY=your-api-key
```

### Core endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check |
| `GET` | `/stats` | Atom / trail / molecule counts |
| `POST` | `/atoms` | Store a memory atom |
| `GET` | `/atoms` | List atoms (`?scope=&q=&limit=`) |
| `GET` | `/atoms/<id>` | Fetch atom by id |
| `DELETE` | `/atoms/<id>` | Soft-delete atom |
| `POST` | `/trails` | Link two atoms (auto-reinforces if exists) |
| `POST` | `/retrieve` | Structural search |
| `POST` | `/retrieve/context` | LLM-ready context bundle |
| `POST` | `/compress` | Compress text → SemaLingua packet |
| `POST` | `/ingest` | Ingest a file path into chunks |
| `POST` | `/decay` | Run trail decay pass |

### Example — store and retrieve

```bash
# Store a memory
curl -X POST http://127.0.0.1:9743/atoms \
  -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/json" \
  -d '{"content": "Switched auth to strict token validation", "importance": 0.8}'

# Retrieve relevant memory (structural)
curl -X POST http://127.0.0.1:9743/retrieve \
  -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/json" \
  -d '{"query": "auth token", "limit": 5}'

# Get LLM-ready context bundle
curl -X POST http://127.0.0.1:9743/retrieve/context \
  -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/json" \
  -d '{"query": "auth token", "compressed": false}'
```

---

## SemaLingua compression

CORTEX-NANO compresses every atom into a [SemaLingua](docs/SEMALINGUA_SPEC.md) packet — an ultra-compact semantic format that preserves meaning without prose.

```
#a1b2c3d4 memory:private
+ strict-token-validation
+ auth-hardening
state: tags:auth,security
intent: harden-auth
posture: importance:0.8
```

- Every atom stores both `content_raw` and `content_compressed`
- Agents can request compressed context bundles to reduce token usage
- Full spec: [`docs/SEMALINGUA_SPEC.md`](docs/SEMALINGUA_SPEC.md)

---

## Ingestion

Supports: OpenClaw JSONL transcripts, markdown notes, plain text, code files.

```bash
cortex-nano ingest ./transcripts --extract smart
cortex-nano ingest ./notes
cortex-nano sync-preview --kind transcript
```

---

## CLI reference

```
cortex-nano [--path ~/.cortex-nano] <command>

Commands:
  init                         Initialize memory store
  ingest <path>                Ingest files (--extract raw|smart)
  search <query>               Search chunks (--limit N)
  sync-preview                 Preview ingestable documents (--kind, --limit)
  serve                        Start local API (--host, --port, --api-key)
  atoms list                   List atoms (--scope, --q, --limit)
  atoms add --content "..."    Create an atom manually
  atoms retrieve --query "..." Structural retrieval
```

---

## Design principles

- **Local-first** — all data stays on device
- **LLM-agnostic** — works with any model
- **Structure-aware** — memory has shape, not just content
- **Meaning-efficient** — SemaLingua keeps context small
- **Inspectable** — everything queryable, nothing hidden
- **Modular** — use the CLI, the API, or import as a library

---

## What's not in v1

- Distributed multi-node memory sync
- Cloud-hosted shared memory
- Autonomous self-tuning
- Full ChromaDB semantic retrieval *(structural only in v0.2)*
- GUI

---

## Roadmap

- [x] Atom / trail / molecule / cell schema
- [x] Structural retrieval with trail + molecule + cell scoring
- [x] SemaLingua compression
- [x] Local HTTP API
- [x] File ingestion pipeline (transcripts, markdown, docs)
- [ ] Molecule auto-formation from trail density
- [ ] ChromaDB semantic retrieval
- [ ] Hybrid retrieval (structural + semantic)
- [ ] `llms.txt` for agent-readable spec
- [ ] Dockerfile

---

## License

MIT
