import argparse
from pathlib import Path
from .store import NanoStore
from .ingest import ingest_path


def cmd_init(args):
    store = NanoStore(Path(args.path).expanduser())
    store.init()
    print(f"initialized cortex-nano at {store.root}")


def cmd_ingest(args):
    store = NanoStore(Path(args.path).expanduser())
    store.init()
    count = ingest_path(store, Path(args.target).expanduser(), extract_mode=args.extract)
    print(f"ingested {count} document(s) with extract={args.extract}")


def cmd_search(args):
    store = NanoStore(Path(args.path).expanduser())
    results = store.search(args.query, limit=args.limit)
    if not results:
        print("no results")
        return
    for row in results:
        print(f"- [{row['kind']}] {row['path']}\n  score={row['score']:.3f}\n  {row['snippet']}\n")


def cmd_sync_preview(args):
    store = NanoStore(Path(args.path).expanduser())
    for row in store.sync_preview(limit=args.limit, kind=args.kind):
        print(f"- [{row['kind']}] {row['path']} :: {row['snippet']}")


def main():
    parser = argparse.ArgumentParser(prog="cortex-nano")
    parser.add_argument("--path", default="~/.cortex-nano")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_init = sub.add_parser("init")
    p_init.set_defaults(func=cmd_init)

    p_ingest = sub.add_parser("ingest")
    p_ingest.add_argument("target")
    p_ingest.add_argument("--extract", choices=["raw", "smart"], default="raw")
    p_ingest.set_defaults(func=cmd_ingest)

    p_search = sub.add_parser("search")
    p_search.add_argument("query")
    p_search.add_argument("--limit", type=int, default=5)
    p_search.set_defaults(func=cmd_search)

    p_sync = sub.add_parser("sync-preview")
    p_sync.add_argument("--limit", type=int, default=10)
    p_sync.add_argument("--kind", choices=["transcript", "session_note", "note", "doc"])
    p_sync.set_defaults(func=cmd_sync_preview)

    args = parser.parse_args()
    args.func(args)
