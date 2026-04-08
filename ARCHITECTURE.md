# CORTEX nano architecture

## Shape
- local ingest
- local chunk store
- local metadata/index
- local retrieval
- manual sync-preview to CORTEX

## Sources
- OpenClaw / agent transcripts
- markdown notes
- project docs

## Data model
- `source_document`
- `chunk`
- `memory_note`
- `sync_candidate`

## Retrieval
v0.1 starts simple:
- chunk text
- store verbatim
- search locally
- return evidence-first results

## Sync model
Manual only in v0.1:
- inspect candidate memories
- preview payload
- upstream push later
