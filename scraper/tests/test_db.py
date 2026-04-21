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

    def test_uiuc_table_exists(self, db):
        cursor = db._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='uiuc_opportunities'"
        )
        assert cursor.fetchone() is not None

    def test_uiuc_index_exists(self, db):
        cursor = db._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_uiuc_seen_at'"
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


# ── UIUC scout persistence ────────────────────────────────────────────

class TestUiucScoutPersistence:

    def test_new_uiuc_opportunity_is_new(self, db):
        assert db.is_new_uiuc("uiuc_seed", "bo-li-trustworthy-ai") is True

    def test_mark_uiuc_seen_and_read_back(self, db):
        opportunity = {
            "id": "uiuc-ml-compiler",
            "title": "Machine Learning Compiler Intern",
            "url": "https://researchpark.illinois.edu/job/ml-compiler/",
            "type": "uiuc_technical_opening",
            "track": "ml_ai_research",
            "org": "Research Park",
            "department": "Research Park",
            "lab": "",
            "faculty_name": "",
            "status": "open",
            "next_action": "apply_now",
            "total_score": 88,
            "company_archetypes": ["Nvidia", "Waymo"],
            "skills": ["Python", "ML systems"],
            "tags": ["machine learning", "compiler"],
            "fit_reasons": ["Matches ML infra direction"],
            "score_components": {"path_fit": 19, "student_accessibility": 10},
            "contact_info": {"email": "", "url": "https://researchpark.illinois.edu/job/ml-compiler/"},
            "description": "Compiler work for ML workloads.",
            "evidence_sources": ["official", "alumni"],
            "alumni_patterns": ["NCSA SPIN"],
            "alumni_evidence_count": 2,
            "should_ping": True,
        }

        db.mark_uiuc_seen("uiuc_jobs", opportunity)

        assert db.is_new_uiuc("uiuc_jobs", "uiuc-ml-compiler") is False

        rows = db.get_recent_uiuc(limit=1)
        assert len(rows) == 1
        row = rows[0]
        assert row["title"] == "Machine Learning Compiler Intern"
        assert row["track"] == "ml_ai_research"
        assert row["type"] == "uiuc_technical_opening"
        assert row["should_ping"] is True
        assert row["company_archetypes"] == ["Nvidia", "Waymo"]
        assert row["score_components"]["path_fit"] == 19
        assert row["evidence_sources"] == ["official", "alumni"]
        assert row["alumni_patterns"] == ["NCSA SPIN"]
        assert row["alumni_evidence_count"] == 2

    def test_get_uiuc_feed_since_returns_only_recent(self, db):
        old = {
            "id": "bo-li-lab",
            "title": "Bo Li Trustworthy AI Lab",
            "url": "https://example.com/bo-li",
            "type": "cold_outreach_target",
            "track": "ml_ai_research",
            "org": "UIUC",
            "department": "CS",
            "lab": "Trustworthy AI Lab",
            "faculty_name": "Bo Li",
            "status": "closed_but_outreachable",
            "next_action": "reach_out",
            "total_score": 81,
            "company_archetypes": ["Anthropic"],
            "skills": ["ML", "Robustness"],
            "tags": ["trustworthy ai"],
            "fit_reasons": ["Matches trustworthy AI interest"],
            "score_components": {"path_fit": 18},
            "contact_info": {"email": "lbo@illinois.edu"},
            "description": "Research on trustworthy AI.",
            "evidence_sources": ["official"],
            "alumni_patterns": [],
            "alumni_evidence_count": 0,
            "should_ping": False,
        }
        new = {
            **old,
            "id": "quant-lab",
            "title": "Quant Research Group",
            "url": "https://example.com/quant",
            "track": "quant_fintech",
            "tags": ["quant", "time series"],
        }

        db.mark_uiuc_seen("uiuc_seed", old)
        cutoff = time.time()
        time.sleep(0.05)
        db.mark_uiuc_seen("uiuc_seed", new)

        rows = db.get_uiuc_feed_since(cutoff)
        assert len(rows) == 1
        assert rows[0]["id"] == "quant-lab"

    def test_get_all_uiuc_returns_snapshot(self, db):
        opportunity = {
            "id": "bo-li-lab",
            "title": "Bo Li",
            "url": "https://example.com/bo-li",
            "type": "cold_outreach_target",
            "track": "ml_ai_research",
            "org": "UIUC",
            "department": "CS",
            "lab": "Trustworthy AI Lab",
            "faculty_name": "Bo Li",
            "status": "rolling",
            "next_action": "reach_out",
            "total_score": 81,
            "company_archetypes": ["Anthropic"],
            "skills": ["machine learning"],
            "tags": ["trustworthy ai"],
            "fit_reasons": ["Matches trustworthy AI interest"],
            "score_components": {"path_fit": 18},
            "contact_info": {"email": "lbo@illinois.edu"},
            "description": "Research on trustworthy AI.",
            "evidence_sources": ["official"],
            "alumni_patterns": [],
            "alumni_evidence_count": 0,
            "should_ping": False,
        }

        db.mark_uiuc_seen("uiuc_seed", opportunity)

        rows = db.get_all_uiuc()

        assert len(rows) == 1
        assert rows[0]["id"] == "bo-li-lab"

    def test_refresh_uiuc_snapshot_prunes_stale_rows_and_preserves_existing_seen_at(self, db):
        existing = {
            "id": "bo-li-lab",
            "title": "Bo Li Trustworthy AI Lab",
            "url": "https://example.com/bo-li",
            "type": "cold_outreach_target",
            "track": "ml_ai_research",
            "org": "UIUC",
            "department": "CS",
            "lab": "Trustworthy AI Lab",
            "faculty_name": "Bo Li",
            "status": "rolling",
            "next_action": "reach_out",
            "total_score": 99,
            "company_archetypes": ["Anthropic"],
            "skills": ["ML"],
            "tags": ["trustworthy ai"],
            "fit_reasons": ["Matches trustworthy AI interest"],
            "score_components": {"path_fit": 20},
            "contact_info": {"email": "lbo@illinois.edu"},
            "description": "Research on trustworthy AI.",
            "evidence_sources": ["official"],
            "alumni_patterns": [],
            "alumni_evidence_count": 0,
            "should_ping": True,
        }
        stale = {
            **existing,
            "id": "stale-item",
            "title": "Stale Item",
            "url": "https://example.com/stale",
        }
        refreshed = {
            **existing,
            "total_score": 104,
            "fit_reasons": ["Matches trustworthy AI interest", "Still active in refreshed snapshot"],
        }
        new = {
            **existing,
            "id": "victor-duarte",
            "title": "Victor Duarte Quant Lab",
            "url": "https://example.com/victor",
            "track": "quant_fintech",
            "tags": ["quant", "time series"],
        }

        db.mark_uiuc_seen("uiuc_seed", existing)
        time.sleep(0.05)
        db.mark_uiuc_seen("research_park_sitemap", stale)
        original_seen_at = db.get_recent_uiuc(limit=2)[1]["seen_at"]

        cutoff = time.time()
        time.sleep(0.05)
        db.refresh_uiuc_snapshot(
            [
                {"source": "uiuc_seed", **refreshed},
                {"source": "uiuc_seed", **new},
            ]
        )

        rows = db.get_recent_uiuc(limit=10)
        ids = {row["id"] for row in rows}
        assert ids == {"bo-li-lab", "victor-duarte"}

        bo_li = next(row for row in rows if row["id"] == "bo-li-lab")
        victor = next(row for row in rows if row["id"] == "victor-duarte")
        assert bo_li["seen_at"] == original_seen_at
        assert bo_li["total_score"] == 104
        assert victor["seen_at"] >= cutoff

    def test_migrate_adds_new_alumni_columns(self, db):
        columns = {
            row["name"]
            for row in db._conn.execute("PRAGMA table_info(uiuc_opportunities)").fetchall()
        }

        assert "evidence_sources" in columns
        assert "alumni_patterns" in columns
        assert "alumni_evidence_count" in columns
