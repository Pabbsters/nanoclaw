"""Simple HTTP server exposing a JSON feed of job postings."""

from __future__ import annotations

import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

from db import PostingDB


class FeedHandler(BaseHTTPRequestHandler):
    """Handler for /feed and /health endpoints."""

    db: PostingDB | None = None

    def do_GET(self) -> None:
        parsed = urlparse(self.path)

        if parsed.path == "/feed" or parsed.path.startswith("/feed"):
            self._handle_feed(parsed.query)
        elif parsed.path == "/health":
            self._handle_health()
        else:
            self.send_error(404)

    def _handle_feed(self, query: str) -> None:
        """Return postings since a given timestamp (default 24h ago)."""
        params = parse_qs(query)
        since_raw = params.get("since", [None])[0]

        if since_raw is not None:
            try:
                since_ts = float(since_raw)
            except (ValueError, TypeError):
                since_ts = time.time() - 86400
        else:
            since_ts = time.time() - 86400

        if self.db is None:
            self._send_json(500, {"error": "database not initialized"})
            return

        postings = self.db.get_feed_since(since_ts)
        body = {
            "postings": postings,
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        self._send_json(200, body)

    def _handle_health(self) -> None:
        self._send_json(200, {"status": "ok"})

    def _send_json(self, status: int, data: dict) -> None:
        payload = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format: str, *args: object) -> None:
        """Suppress default stderr logging."""


def start_feed_server(db: PostingDB, port: int = int(os.environ.get("PORT", "8080"))) -> HTTPServer:
    """Start the feed server in a background daemon thread."""
    FeedHandler.db = db
    server = HTTPServer(("0.0.0.0", port), FeedHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server
