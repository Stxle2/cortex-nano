"""
Cortex Nano — local HTTP API (stdlib only, zero extra deps).

Endpoints OpenClaw uses:
  GET  /health
  GET  /stats
  POST /atoms
  GET  /atoms
  GET  /atoms/<id>
  DELETE /atoms/<id>
  POST /trails
  POST /retrieve          — structural search
  POST /ingest            — ingest a file path into documents/chunks
"""

from __future__ import annotations

import json
import os
import re
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .retrieval import structural_retrieve
from .store import NanoStore


def _make_handler(store: NanoStore, api_key: str | None):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            pass  # silence default access log; errors still go to stderr

        # ── Auth ──────────────────────────────────────────────────────────────

        def _check_auth(self) -> bool:
            if not api_key:
                return True
            header = self.headers.get("Authorization", "")
            m = re.match(r"Bearer\s+(.+)", header, re.IGNORECASE)
            if m and m.group(1).strip() == api_key:
                return True
            self._send({"ok": False, "error": "Unauthorized"}, 401)
            return False

        # ── Response helpers ──────────────────────────────────────────────────

        def _send(self, payload: dict | list, status: int = 200):
            body = json.dumps(payload, ensure_ascii=False, default=str).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _body(self) -> dict:
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length) if length else b"{}"
            try:
                return json.loads(raw)
            except Exception:
                return {}

        # ── Routing ───────────────────────────────────────────────────────────

        def _route(self, method: str):
            parsed = urlparse(self.path)
            path = parsed.path.rstrip("/")
            qs = parse_qs(parsed.query)

            # GET /health
            if method == "GET" and path == "/health":
                self._send({"ok": True, "status": "running", "version": "0.2.0"})
                return

            # GET /stats
            if method == "GET" and path == "/stats":
                if not self._check_auth():
                    return
                self._send({"ok": True, **store.atom_stats()})
                return

            # POST /atoms
            if method == "POST" and path == "/atoms":
                if not self._check_auth():
                    return
                b = self._body()
                content = (b.get("content") or "").strip()
                if not content:
                    self._send({"ok": False, "error": "content required"}, 422)
                    return
                atom = store.create_atom(
                    content=content,
                    scope=b.get("scope", "private"),
                    importance=float(b.get("importance", 0.5)),
                    source_type=b.get("source_type"),
                    source_ref=b.get("source_ref"),
                    tags=b.get("tags"),
                )
                self._send({"ok": True, "atom": atom}, 201)
                return

            # GET /atoms
            if method == "GET" and path == "/atoms":
                if not self._check_auth():
                    return
                scope = qs.get("scope", ["private"])[0]
                q = qs.get("q", [""])[0]
                limit = int(qs.get("limit", [20])[0])
                atoms = store.list_atoms(scope=scope, q=q, limit=limit)
                self._send({"ok": True, "data": atoms, "count": len(atoms)})
                return

            # GET /atoms/<id>
            m = re.fullmatch(r"/atoms/([^/]+)", path)
            if method == "GET" and m:
                if not self._check_auth():
                    return
                atom = store.fetch_atom(m.group(1))
                if atom is None:
                    self._send({"ok": False, "error": "not found"}, 404)
                    return
                self._send({"ok": True, "atom": atom})
                return

            # DELETE /atoms/<id>
            if method == "DELETE" and m:
                if not self._check_auth():
                    return
                store.delete_atom(m.group(1))
                self._send({"ok": True})
                return

            # POST /trails
            if method == "POST" and path == "/trails":
                if not self._check_auth():
                    return
                b = self._body()
                from_id = (b.get("from_id") or "").strip()
                to_id = (b.get("to_id") or "").strip()
                if not from_id or not to_id:
                    self._send({"ok": False, "error": "from_id and to_id required"}, 422)
                    return
                trail = store.create_or_reinforce_trail(
                    from_id=from_id,
                    to_id=to_id,
                    scope=b.get("scope", "private"),
                    weight=float(b.get("weight", 0.5)),
                    link_reason=b.get("link_reason"),
                )
                self._send({"ok": True, "trail": trail}, 201)
                return

            # POST /retrieve
            if method == "POST" and path == "/retrieve":
                if not self._check_auth():
                    return
                b = self._body()
                try:
                    results = structural_retrieve(
                        store,
                        query=b.get("query", ""),
                        seed_atom_id=b.get("seed_atom_id", ""),
                        scope=b.get("scope", "private"),
                        limit=int(b.get("limit", 10)),
                    )
                except ValueError as e:
                    self._send({"ok": False, "error": str(e)}, 422)
                    return
                self._send({"ok": True, "results": results, "count": len(results)})
                return

            # POST /ingest
            if method == "POST" and path == "/ingest":
                if not self._check_auth():
                    return
                b = self._body()
                target = (b.get("path") or "").strip()
                if not target:
                    self._send({"ok": False, "error": "path required"}, 422)
                    return
                from .ingest import ingest_path
                count = ingest_path(store, Path(target).expanduser(),
                                    extract_mode=b.get("extract", "raw"))
                self._send({"ok": True, "ingested": count})
                return

            # POST /decay
            if method == "POST" and path == "/decay":
                if not self._check_auth():
                    return
                b = self._body()
                result = store.decay_trails(scope=b.get("scope", "private"))
                self._send({"ok": True, **result})
                return

            self._send({"ok": False, "error": "not found"}, 404)

        def do_GET(self):    self._route("GET")
        def do_POST(self):   self._route("POST")
        def do_DELETE(self): self._route("DELETE")

    return Handler


def serve(store: NanoStore, host: str = "127.0.0.1", port: int = 9743,
          api_key: str | None = None):
    handler = _make_handler(store, api_key)
    httpd = HTTPServer((host, port), handler)
    print(f"cortex-nano listening on http://{host}:{port}")
    if not api_key:
        print("  warning: no CORTEX_NANO_API_KEY set — API is open")
    httpd.serve_forever()
