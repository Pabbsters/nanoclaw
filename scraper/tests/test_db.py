"""Tests for the PostingDB persistence layer."""

from __future__ import annotations

import os
import tempfile
import time

import pytest

from db import PostingDB


@pytest.fixture()
def db_path(tmp_path):
    """Return a temporary database file path."""
    return str(tmp_path / "test_postings.db")


@pytest.fixture()
def db(db_path):
    """Create a fresh PostingDB instance and close it after the test."""
    database = PostingDB(path=db_path)
    yield database
    database.close()


# ── Table creation ─────────────────────────────────────────────────────

class TestTableCreation:

    def test_creates_database_file(self, db, db_path):
        assert os.path.exists(db_path)

    def test_table_exists(self, db):
        cursor = db._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='seen_postings'"
        )
        assert cursor.fetchone() is not None

    def test_index_exists(self, db):
        cursor = db._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_seen_at'"
        )
        assert cursor.fetchone() is not None


# ── is_new / mark_seen ────────────────────────────────────────────────

class TestIsNewAndMarkSeen:

    def test_new_posting_is_new(self, db):
        assert db.is_new("greenhouse", "citadel", "12345") is True

    def test_after_mark_seen_not_new(self, db):
        db.mark_seen("greenhouse", "citadel", "12345", "SWE Intern", "https://example.com")
        assert db.is_new("greenhouse", "citadel", "12345") is False

    def test_different_posting_still_new(self, db):
        db.mark_seen("greenhouse", "citadel", "12345", "SWE Intern", "https://example.com")
        assert db.is_new("greenhouse", "citadel", "99999") is True

    def test_different_source_still_new(self, db):
        db.mark_seen("greenhouse", "citadel", "12345", "SWE Intern", "https://example.com")
        assert db.is_new("ashby", "citadel", "12345") is True

    def test_duplicate_mark_seen_no_error(self, db):
        db.mark_seen("greenhouse", "citadel", "12345", "SWE Intern", "https://example.com")
        # Should not raise on duplicate
        db.mark_seen("greenhouse", "citadel", "12345", "SWE Intern", "https://example.com")
        assert db.is_new("greenhouse", "citadel", "12345") is False


# ── mark_seen with optional fields ───────────────────────────────────

class TestMarkSeenOptionalFields:

    def test_all_optional_fields_stored(self, db):
        db.mark_seen(
            source="greenhouse",
            company_slug="citadel",
            posting_id="100",
            title="ML Engineer",
            url="https://example.com/100",
            track="ai_data",
            company_name="Citadel",
            skills="Python, PyTorch",
            comp="$150k",
            team="Quant Research",
            deadline="2026-06-01",
        )
        rows = db.get_recent(limit=1)
        assert len(rows) == 1
        row = rows[0]
        assert row["track"] == "ai_data"
        assert row["company_name"] == "Citadel"
        assert row["skills"] == "Python, PyTorch"
        assert row["comp"] == "$150k"
        assert row["team"] == "Quant Research"
        assert row["deadline"] == "2026-06-01"


# ── get_recent ────────────────────────────────────────────────────────

class TestGetRecent:

    def test_empty_db_returns_empty(self, db):
        assert db.get_recent() == []

    def test_returns_dicts(self, db):
        db.mark_seen("gh", "citadel", "1", "Title", "https://url")
        rows = db.get_recent(limit=1)
        assert isinstance(rows, list)
        assert isinstance(rows[0], dict)

    def test_respects_limit(self, db):
        for i in range(10):
            db.mark_seen("gh", "citadel", str(i), f"Title {i}", f"https://url/{i}")
        assert len(db.get_recent(limit=3)) == 3

    def test_ordered_by_seen_at_desc(self, db):
        db.mark_seen("gh", "a", "1", "First", "https://url/1")
        time.sleep(0.05)
        db.mark_seen("gh", "b", "2", "Second", "https://url/2")
        rows = db.get_recent(limit=2)
        assert rows[0]["title"] == "Second"
        assert rows[1]["title"] == "First"


# ── get_feed_since ────────────────────────────────────────────────────

class TestGetFeedSince:

    def test_returns_only_recent(self, db):
        db.mark_seen("gh", "a", "1", "Old", "https://url/1")
        cutoff = time.time()
        time.sleep(0.05)
        db.mark_seen("gh", "b", "2", "New", "https://url/2")
        rows = db.get_feed_since(cutoff)
        assert len(rows) == 1
        assert rows[0]["title"] == "New"

    def test_empty_when_none_since(self, db):
        db.mark_seen("gh", "a", "1", "Old", "https://url/1")
        rows = db.get_feed_since(time.time() + 100)
        assert rows == []


# ── close ─────────────────────────────────────────────────────────────

class TestClose:

    def test_close_is_idempotent(self, db):
        db.close()
        db.close()  # Should not raise
