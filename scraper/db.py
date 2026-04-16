"""SQLite persistence layer for tracking seen postings."""

from __future__ import annotations

import os
import sqlite3
import time
import json
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

_CREATE_UIUC_TABLE = """
CREATE TABLE IF NOT EXISTS uiuc_opportunities (
    source             TEXT    NOT NULL,
    opportunity_id     TEXT    NOT NULL,
    title              TEXT    NOT NULL DEFAULT '',
    url                TEXT    NOT NULL DEFAULT '',
    type               TEXT    NOT NULL DEFAULT '',
    track              TEXT    NOT NULL DEFAULT '',
    org                TEXT    NOT NULL DEFAULT '',
    department         TEXT    NOT NULL DEFAULT '',
    lab                TEXT    NOT NULL DEFAULT '',
    faculty_name       TEXT    NOT NULL DEFAULT '',
    status             TEXT    NOT NULL DEFAULT '',
    next_action        TEXT    NOT NULL DEFAULT '',
    total_score        REAL    NOT NULL DEFAULT 0,
    company_archetypes TEXT    NOT NULL DEFAULT '[]',
    skills             TEXT    NOT NULL DEFAULT '[]',
    tags               TEXT    NOT NULL DEFAULT '[]',
    fit_reasons        TEXT    NOT NULL DEFAULT '[]',
    score_components   TEXT    NOT NULL DEFAULT '{}',
    contact_info       TEXT    NOT NULL DEFAULT '{}',
    description        TEXT    NOT NULL DEFAULT '',
    evidence_sources   TEXT    NOT NULL DEFAULT '[]',
    alumni_patterns    TEXT    NOT NULL DEFAULT '[]',
    alumni_evidence_count INTEGER NOT NULL DEFAULT 0,
    should_ping        INTEGER NOT NULL DEFAULT 0,
    seen_at            REAL    NOT NULL,
    PRIMARY KEY (source, opportunity_id)
)
"""

_CREATE_UIUC_INDEX = """
CREATE INDEX IF NOT EXISTS idx_uiuc_seen_at ON uiuc_opportunities (seen_at)
"""


class PostingDB:
    """Thin wrapper around a SQLite database of seen job postings."""

    def __init__(self, path: str = "postings.db") -> None:
        parent = os.path.dirname(os.path.abspath(path))
        os.makedirs(parent, exist_ok=True)
        self._conn: Optional[sqlite3.Connection] = sqlite3.connect(path, check_same_thread=False)
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

    def is_new_uiuc(self, source: str, opportunity_id: str) -> bool:
        """Return True if this UIUC opportunity has never been seen."""
        cursor = self._conn.execute(
            "SELECT 1 FROM uiuc_opportunities WHERE source = ? AND opportunity_id = ?",
            (source, opportunity_id),
        )
        return cursor.fetchone() is None

    def mark_uiuc_seen(self, source: str, opportunity: dict) -> None:
        """Record a UIUC opportunity as seen (upsert)."""
        self._conn.execute(
            "INSERT OR REPLACE INTO uiuc_opportunities "
            "(source, opportunity_id, title, url, type, track, org, department, lab, "
            " faculty_name, status, next_action, total_score, company_archetypes, skills, "
            " tags, fit_reasons, score_components, contact_info, description, evidence_sources, "
            " alumni_patterns, alumni_evidence_count, should_ping, seen_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                source,
                opportunity.get("id", ""),
                opportunity.get("title", ""),
                opportunity.get("url", ""),
                opportunity.get("type", ""),
                opportunity.get("track", ""),
                opportunity.get("org", ""),
                opportunity.get("department", ""),
                opportunity.get("lab", ""),
                opportunity.get("faculty_name", ""),
                opportunity.get("status", ""),
                opportunity.get("next_action", ""),
                float(opportunity.get("total_score", 0)),
                json.dumps(opportunity.get("company_archetypes", [])),
                json.dumps(opportunity.get("skills", [])),
                json.dumps(opportunity.get("tags", [])),
                json.dumps(opportunity.get("fit_reasons", [])),
                json.dumps(opportunity.get("score_components", {})),
                json.dumps(opportunity.get("contact_info", {})),
                opportunity.get("description", ""),
                json.dumps(opportunity.get("evidence_sources", [])),
                json.dumps(opportunity.get("alumni_patterns", [])),
                int(opportunity.get("alumni_evidence_count", 0) or 0),
                1 if opportunity.get("should_ping") else 0,
                time.time(),
            ),
        )
        self._conn.commit()

    def get_recent_uiuc(self, limit: int = 50) -> list[dict]:
        """Return the most recent UIUC opportunities, newest first."""
        cursor = self._conn.execute(
            "SELECT * FROM uiuc_opportunities ORDER BY seen_at DESC LIMIT ?",
            (limit,),
        )
        return [self._deserialize_uiuc_row(dict(row)) for row in cursor.fetchall()]

    def get_uiuc_feed_since(self, since_ts: float) -> list[dict]:
        """Return all UIUC opportunities seen after *since_ts*."""
        cursor = self._conn.execute(
            "SELECT * FROM uiuc_opportunities WHERE seen_at > ? ORDER BY seen_at ASC",
            (since_ts,),
        )
        return [self._deserialize_uiuc_row(dict(row)) for row in cursor.fetchall()]

    def refresh_uiuc_snapshot(self, opportunities: list[dict]) -> None:
        """Replace the live UIUC snapshot while preserving original seen_at for existing rows."""
        cursor = self._conn.execute(
            "SELECT source, opportunity_id, seen_at FROM uiuc_opportunities"
        )
        existing_seen_at = {
            (row["source"], row["opportunity_id"]): row["seen_at"]
            for row in cursor.fetchall()
        }
        now = time.time()

        self._conn.execute("DELETE FROM uiuc_opportunities")
        for opportunity in opportunities:
            source = str(opportunity.get("source", "uiuc_scout"))
            opportunity_id = str(opportunity.get("id", ""))
            seen_at = existing_seen_at.get((source, opportunity_id), now)
            self._conn.execute(
                "INSERT OR REPLACE INTO uiuc_opportunities "
                "(source, opportunity_id, title, url, type, track, org, department, lab, "
                " faculty_name, status, next_action, total_score, company_archetypes, skills, "
                " tags, fit_reasons, score_components, contact_info, description, evidence_sources, "
                " alumni_patterns, alumni_evidence_count, should_ping, seen_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    source,
                    opportunity_id,
                    opportunity.get("title", ""),
                    opportunity.get("url", ""),
                    opportunity.get("type", ""),
                    opportunity.get("track", ""),
                    opportunity.get("org", ""),
                    opportunity.get("department", ""),
                    opportunity.get("lab", ""),
                    opportunity.get("faculty_name", ""),
                    opportunity.get("status", ""),
                    opportunity.get("next_action", ""),
                    float(opportunity.get("total_score", 0)),
                    json.dumps(opportunity.get("company_archetypes", [])),
                    json.dumps(opportunity.get("skills", [])),
                    json.dumps(opportunity.get("tags", [])),
                    json.dumps(opportunity.get("fit_reasons", [])),
                    json.dumps(opportunity.get("score_components", {})),
                    json.dumps(opportunity.get("contact_info", {})),
                    opportunity.get("description", ""),
                    json.dumps(opportunity.get("evidence_sources", [])),
                    json.dumps(opportunity.get("alumni_patterns", [])),
                    int(opportunity.get("alumni_evidence_count", 0) or 0),
                    1 if opportunity.get("should_ping") else 0,
                    seen_at,
                ),
            )
        self._conn.commit()

    # ── private ────────────────────────────────────────────────────

    def _migrate(self) -> None:
        self._conn.execute(_CREATE_TABLE)
        self._conn.execute(_CREATE_INDEX)
        self._conn.execute(_CREATE_UIUC_TABLE)
        self._conn.execute(_CREATE_UIUC_INDEX)
        self._ensure_uiuc_columns()
        self._conn.commit()

    def _deserialize_uiuc_row(self, row: dict) -> dict:
        row["company_archetypes"] = json.loads(row.get("company_archetypes", "[]"))
        row["skills"] = json.loads(row.get("skills", "[]"))
        row["tags"] = json.loads(row.get("tags", "[]"))
        row["fit_reasons"] = json.loads(row.get("fit_reasons", "[]"))
        row["score_components"] = json.loads(row.get("score_components", "{}"))
        row["contact_info"] = json.loads(row.get("contact_info", "{}"))
        row["evidence_sources"] = json.loads(row.get("evidence_sources", "[]"))
        row["alumni_patterns"] = json.loads(row.get("alumni_patterns", "[]"))
        row["alumni_evidence_count"] = int(row.get("alumni_evidence_count", 0) or 0)
        row["should_ping"] = bool(row.get("should_ping"))
        row["id"] = row.pop("opportunity_id")
        return row

    def _ensure_uiuc_columns(self) -> None:
        existing_columns = {
            row["name"]
            for row in self._conn.execute("PRAGMA table_info(uiuc_opportunities)").fetchall()
        }
        desired_columns = {
            "evidence_sources": "TEXT NOT NULL DEFAULT '[]'",
            "alumni_patterns": "TEXT NOT NULL DEFAULT '[]'",
            "alumni_evidence_count": "INTEGER NOT NULL DEFAULT 0",
        }
        for column_name, column_def in desired_columns.items():
            if column_name in existing_columns:
                continue
            self._conn.execute(
                f"ALTER TABLE uiuc_opportunities ADD COLUMN {column_name} {column_def}"
            )
