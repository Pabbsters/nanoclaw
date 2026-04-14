"""JobSpy aggregator poller for multiple job boards."""

from __future__ import annotations

from jobspy import scrape_jobs

SEARCH_QUERIES: list[str] = [
    "AI engineer intern",
    "machine learning intern",
    "data engineer intern",
    "data scientist intern",
    "software engineer intern",
    "cloud engineer intern",
    "cybersecurity intern",
    "solutions architect intern",
    "quant intern",
]

SITES: list[str] = ["indeed", "google", "zip_recruiter"]


def _normalize_row(row: dict) -> dict:
    """Convert a JobSpy row to a normalized posting dict."""
    url = str(row.get("job_url", ""))
    return {
        "posting_id": str(row.get("id", hash(url))),
        "title": str(row.get("title", "")),
        "url": url,
        "company_slug": str(row.get("company", "")).lower().replace(" ", "-"),
        "company_name": str(row.get("company", "")),
        "location": str(row.get("location", "")),
        "description": str(row.get("description", ""))[:500],
        "skills": "",
        "team": "",
    }


def poll_jobspy() -> list[dict]:
    """Run JobSpy searches and return normalized posting dicts.

    Note: JobSpy is sync, not async.
    """
    all_jobs: list[dict] = []

    for query in SEARCH_QUERIES:
        try:
            jobs_df = scrape_jobs(
                site_name=SITES,
                search_term=query,
                location="United States",
                results_wanted=30,
                hours_old=24,
            )
            for _, row in jobs_df.iterrows():
                all_jobs.append(_normalize_row(row.to_dict()))
        except Exception:
            continue

    return all_jobs
