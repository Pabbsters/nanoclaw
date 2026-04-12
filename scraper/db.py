"""SQLite persistence layer for tracking seen postings."""

from __future__ import annotations

import sqlite3
import time
from typing import Optional


_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS seen_postings (
    source        TEXT    NOT NULL,
    company_slug  TEXT    NOT NULL,
    posting_id    TEXT    NOT NULL,
    title         TEXT    NOT NULL DEFAULT '',
    url           TEXT    NOT NULL DEFAULT '',
    track         TEXT    NOT NULL DEFAULT '',
    company_name  TEXT    NOT NULL DEFAULT '',
    skills        TEXT    NOT NULL DEFAULT '',
    comp          TEXT    NOT NULL DEFAULT '',
    team          TEXT    NOT NULL DEFAULT '',
    deadline      TEXT    NOT NULL DEFAULT '',
    seen_at       REAL    NOT NULL,
    PRIMARY KEY (source, company_slug, posting_id)
)
"""

_CREATE_INDEX = """
CREATE INDEX IF NOT EXISTS idx_seen_at ON seen_postings (seen_at)
"""


class PostingDB:
    """Thin wrapper around a SQLite database of seen job postings."""

    def __init__(self, path: str = "postings.db") -> None:
        self._conn: Optional[sqlite3.Connection] = sqlite3.connect(path)
        self._conn.row_factory = sqlite3.Row
        self._migrate()

    # ── public API ─────────────────────────────────────────────────

    def is_new(self, source: str, company_slug: str, posting_id: str) -> bool:
        """Return True if this posting has never been seen."""
        cursor = self._conn.execute(
            "SELECT 1 FROM seen_postings "
            "WHERE source = ? AND company_slug = ? AND posting_id = ?",
            (source, company_slug, posting_id),
        )
        return cursor.fetchone() is None

    def mark_seen(
        self,
        source: str,
        company_slug: str,
        posting_id: str,
        title: str,
        url: str,
        track: str = "",
        company_name: str = "",
        skills: str = "",
        comp: str = "",
        team: str = "",
        deadline: str = "",
    ) -> None:
        """Record a posting as seen (upsert)."""
        self._conn.execute(
            "INSERT OR REPLACE INTO seen_postings "
            "(source, company_slug, posting_id, title, url, "
            " track, company_name, skills, comp, team, deadline, seen_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                source, company_slug, posting_id, title, url,
                track, company_name, skills, comp, team, deadline,
                time.time(),
            ),
        )
        self._conn.commit()

    def get_recent(self, limit: int = 50) -> list[dict]:
        """Return the most recent postings, newest first."""
        cursor = self._conn.execute(
            "SELECT * FROM seen_postings ORDER BY seen_at DESC LIMIT ?",
            (limit,),
        )
        return [dict(row) for row in cursor.fetchall()]

    def get_feed_since(self, since_ts: float) -> list[dict]:
        """Return all postings seen after *since_ts* (unix timestamp)."""
        cursor = self._conn.execute(
            "SELECT * FROM seen_postings WHERE seen_at > ? ORDER BY seen_at ASC",
            (since_ts,),
        )
        return [dict(row) for row in cursor.fetchall()]

    def close(self) -> None:
        """Close the database connection (idempotent)."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    # ── private ────────────────────────────────────────────────────

    def _migrate(self) -> None:
        self._conn.execute(_CREATE_TABLE)
        self._conn.execute(_CREATE_INDEX)
        self._conn.commit()
