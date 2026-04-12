import argparse
import os
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


def cmd_serve(args):
    from .api import serve
    store = NanoStore(Path(args.path).expanduser())
    store.init()
    api_key = args.api_key or os.environ.get("CORTEX_NANO_API_KEY")
    serve(store, host=args.host, port=args.port, api_key=api_key)


def cmd_atoms(args):
    from .retrieval import structural_retrieve
    store = NanoStore(Path(args.path).expanduser())
    if args.atoms_cmd == "list":
        atoms = store.list_atoms(scope=args.scope, q=args.q or "", limit=args.limit)
        if not atoms:
            print("no atoms")
            return
        for a in atoms:
            print(f"- [{a['id'][:8]}] importance={a['importance']:.2f}  {a['content_raw'][:120]}")
    elif args.atoms_cmd == "add":
        atom = store.create_atom(content=args.content, scope=args.scope,
                                 importance=float(args.importance))
        print(f"created atom {atom['id']}")
    elif args.atoms_cmd == "retrieve":
        results = structural_retrieve(store, query=args.query, scope=args.scope, limit=args.limit)
        if not results:
            print("no results")
            return
        for r in results:
            print(f"- score={r['score']:.3f}  [{r['atom']['id'][:8]}]  {r['atom']['content_raw'][:120]}")


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

    p_serve = sub.add_parser("serve")
    p_serve.add_argument("--host", default="127.0.0.1")
    p_serve.add_argument("--port", type=int, default=9743)
    p_serve.add_argument("--api-key", default=None)
    p_serve.set_defaults(func=cmd_serve)

    p_atoms = sub.add_parser("atoms")
    p_atoms.add_argument("atoms_cmd", choices=["list", "add", "retrieve"])
    p_atoms.add_argument("--scope", default="private")
    p_atoms.add_argument("--limit", type=int, default=10)
    p_atoms.add_argument("--q", default=None)
    p_atoms.add_argument("--query", default="")
    p_atoms.add_argument("--content", default="")
    p_atoms.add_argument("--importance", default="0.5")
    p_atoms.set_defaults(func=cmd_atoms)

    args = parser.parse_args()
    args.func(args)
