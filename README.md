# CORTEX nano

Local-first memory for agent transcripts, markdown notes, and project docs.

## v0.1
- CLI only
- ingest OpenClaw-style transcripts, markdown, and project docs
- local semantic search
- verbatim evidence retention
- manual sync preview for upstream CORTEX

## Commands
- `cortex-nano init`
- `cortex-nano ingest <path>`
- `cortex-nano search <query>`
- `cortex-nano sync-preview`

## Storage
- SQLite metadata DB
- local files for raw chunks
- local embeddings index (pluggable in v0.1)

## Goal
Keep raw/private memory local. Push only selected durable memory upstream later.
