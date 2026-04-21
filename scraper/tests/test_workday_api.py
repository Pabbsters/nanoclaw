"""Tests for the Workday CXS API poller."""

from __future__ import annotations

from sources.workday_api import is_intern_posting, parse_workday_api_jobs


def test_is_intern_posting_matches_coop() -> None:
    assert is_intern_posting("Data Engineering Co-op") is True


def test_parse_workday_api_jobs_filters_and_normalizes() -> None:
    raw = {
        "jobPostings": [
            {
                "title": "Software Engineering Internship",
                "externalPath": "/job/Fremont/Software-Engineering-Internship_12345",
                "locationsText": "Fremont, California",
                "postedOn": "2026-04-20",
                "bulletFields": ["12345"],
            },
            {
                "title": "Staff Machine Learning Engineer",
                "externalPath": "/job/Palo-Alto/Staff-ML-Engineer_99999",
                "locationsText": "Palo Alto, California",
                "postedOn": "2026-04-18",
                "bulletFields": ["99999"],
            },
            {
                "title": "Data Engineering Co-op",
                "externalPath": "/job/Austin/Data-Engineering-Coop_22222",
                "jobLocations": ["Austin, Texas", "Remote"],
                "postedOn": "Posted 3 Days Ago",
                "bulletFields": ["22222"],
            },
        ]
    }

    results = parse_workday_api_jobs("tesla", "Tesla", "tesla.wd1.myworkdayjobs.com", raw)

    assert [job["posting_id"] for job in results] == ["12345", "22222"]
    assert results[0]["url"] == "https://tesla.wd1.myworkdayjobs.com/job/Fremont/Software-Engineering-Internship_12345"
    assert results[0]["posted_at"] == "2026-04-20"
    assert results[1]["location"] == "Austin, Texas, Remote"
    assert results[1]["posted_at"] == ""
