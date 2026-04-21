"""Tests for the UIUC alumni intelligence helpers."""

from __future__ import annotations

import json

from uiuc_alumni import (
    apply_alumni_feedback,
    build_alumni_patterns,
    build_source_records_from_alumni_patterns,
    load_alumni_profile_records,
    normalize_linkedin_profile_record,
)


def test_normalize_linkedin_profile_record_keeps_relevant_uiuc_profile() -> None:
    record = {
        "source": "public_linkedin_collector",
        "profile_url": "https://www.linkedin.com/in/alice-illinois/",
        "name": "Alice Illinois",
        "headline": "UIUC CS student doing ML research at NCSA",
        "education": ["University of Illinois Urbana-Champaign"],
        "current_org": "NCSA",
        "research_orgs": ["Bo Li Lab"],
        "projects": ["RAG evaluation platform"],
        "skills": ["Python", "PyTorch"],
        "resource_signals": [
            {"name": "NCSA SPIN", "entity_type": "program"},
            {"name": "Research Park", "entity_type": "resource"},
        ],
    }

    normalized = normalize_linkedin_profile_record(record)

    assert normalized is not None
    assert normalized["education_matches_uiuc"] is True
    assert "ml_ai_research" in normalized["path_tags"]
    assert normalized["resource_signals"][0]["entity_name"] == "NCSA SPIN"
    assert normalized["evidence_provider"] == "public_linkedin"


def test_load_alumni_profile_records_reads_list_payload(tmp_path) -> None:
    payload = [
        {
            "profile_url": "https://linkedin.example/alice",
            "name": "Alice Illinois",
        }
    ]
    path = tmp_path / "profiles.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    records = load_alumni_profile_records(str(path))

    assert len(records) == 1
    assert records[0]["name"] == "Alice Illinois"


def test_load_alumni_profile_records_reads_directory_payloads(tmp_path) -> None:
    first = tmp_path / "a.json"
    second = tmp_path / "b.json"
    first.write_text(json.dumps([{"profile_url": "https://linkedin.example/alice", "name": "Alice Illinois"}]), encoding="utf-8")
    second.write_text(json.dumps([{"profile_url": "https://linkedin.example/bob", "name": "Bob Illinois"}]), encoding="utf-8")

    records = load_alumni_profile_records(str(tmp_path))

    assert len(records) == 2


def test_normalize_linkedin_profile_record_filters_non_uiuc_profile() -> None:
    record = {
        "profile_url": "https://linkedin.example/bob",
        "name": "Bob Elsewhere",
        "headline": "Machine learning intern",
        "education": ["Purdue University"],
        "current_org": "Startup",
    }

    assert normalize_linkedin_profile_record(record) is None


def test_build_alumni_patterns_aggregates_repeated_resources() -> None:
    profiles = [
        normalize_linkedin_profile_record(
            {
                "source": "public_linkedin_collector",
                "profile_url": "https://www.linkedin.com/in/alice-illinois/",
                "name": "Alice Illinois",
                "headline": "UIUC ML researcher",
                "education": ["University of Illinois Urbana-Champaign"],
                "research_orgs": ["Bo Li Lab"],
                "resource_signals": [{"name": "NCSA SPIN", "entity_type": "program"}],
            }
        ),
        normalize_linkedin_profile_record(
            {
                "source": "public_linkedin_collector",
                "profile_url": "https://www.linkedin.com/in/carol-illinois/",
                "name": "Carol Illinois",
                "headline": "UIUC AI researcher",
                "education": ["UIUC"],
                "research_orgs": ["Bo Li Lab"],
                "resource_signals": [{"name": "NCSA SPIN", "entity_type": "program"}],
            }
        ),
    ]
    profiles = [profile for profile in profiles if profile is not None]

    patterns = build_alumni_patterns(profiles)

    ncsa_spin = next(pattern for pattern in patterns if pattern["entity_name"] == "NCSA SPIN")
    bo_li_lab = next(pattern for pattern in patterns if pattern["entity_name"] == "Bo Li Lab")
    assert ncsa_spin["evidence_count"] == 2
    assert ncsa_spin["recommended_action"] == "reach_out"
    assert bo_li_lab["evidence_count"] == 2
    assert ncsa_spin["linkedin_backing_count"] == 2


def test_build_alumni_patterns_merges_same_entity_across_signal_types() -> None:
    profiles = [
        normalize_linkedin_profile_record(
            {
                "profile_url": "https://linkedin.example/alice",
                "name": "Alice Illinois",
                "headline": "UIUC SWE via Research Park",
                "education": ["University of Illinois Urbana-Champaign"],
                "current_org": "Research Park",
            }
        ),
        normalize_linkedin_profile_record(
            {
                "profile_url": "https://linkedin.example/carol",
                "name": "Carol Illinois",
                "headline": "UIUC AI builder",
                "education": ["UIUC"],
                "resource_signals": [{"name": "Research Park", "entity_type": "resource"}],
            }
        ),
    ]
    profiles = [profile for profile in profiles if profile is not None]

    patterns = [pattern for pattern in build_alumni_patterns(profiles) if pattern["entity_name"] == "Research Park"]

    assert len(patterns) == 1
    assert patterns[0]["evidence_count"] == 2


def test_build_source_records_from_alumni_patterns_surfaces_new_uiuc_sources() -> None:
    patterns = [
        {
            "id": "program:ncsa-spin",
            "entity_type": "program",
            "entity_name": "NCSA SPIN",
            "entity_url": "https://spin.ncsa.illinois.edu/",
            "evidence_count": 3,
            "sample_profiles": [],
            "path_tags": ["ml_ai_research"],
            "fit_reasons": ["Repeated UIUC pattern"],
            "recommended_action": "reach_out",
            "score": 44,
            "illinois_connected": True,
        }
    ]

    records = build_source_records_from_alumni_patterns(patterns)

    assert len(records) == 1
    assert records[0]["source"] == "uiuc_alumni_pattern"
    assert records[0]["title"] == "NCSA SPIN"
    assert records[0]["entity_kind"] == "research_program"


def test_apply_alumni_feedback_boosts_matching_official_opportunity() -> None:
    opportunities = [
        {
            "id": "bo-li",
            "title": "Bo Li - Trustworthy AI",
            "url": "https://example.com/bo-li",
            "type": "cold_outreach_target",
            "track": "ml_ai_research",
            "org": "UIUC",
            "department": "CS",
            "lab": "Bo Li Lab",
            "faculty_name": "Bo Li",
            "status": "rolling",
            "next_action": "reach_out",
            "total_score": 90,
            "company_archetypes": ["Anthropic"],
            "skills": ["machine learning"],
            "tags": ["trustworthy ai"],
            "fit_reasons": ["Trustworthy AI fit"],
            "score_components": {
                "path_fit": 20,
                "skill_growth_fit": 16,
                "evidence_fit": 15,
                "work_shape_similarity": 10,
                "uiuc_relevance": 10,
                "student_accessibility": 10,
                "actionability": 8,
                "freshness": 4,
            },
            "contact_info": {"url": "https://example.com/bo-li"},
            "description": "Trustworthy AI research at UIUC.",
            "evidence_sources": ["official"],
            "alumni_patterns": [],
            "alumni_evidence_count": 0,
            "should_ping": False,
        }
    ]
    patterns = [
        {
            "id": "lab:bo-li-lab",
            "entity_type": "lab",
            "entity_name": "Bo Li Lab",
            "entity_url": "",
            "evidence_count": 3,
            "sample_profiles": [],
            "path_tags": ["ml_ai_research"],
            "fit_reasons": ["Repeated lab"],
            "recommended_action": "reach_out",
            "score": 42,
            "illinois_connected": True,
            "evidence_providers": ["browser_assisted_linkedin"],
            "provider_counts": {"browser_assisted_linkedin": 3},
            "linkedin_backing_count": 3,
            "source_strength": 9,
        }
    ]

    enriched = apply_alumni_feedback(opportunities, patterns)

    assert enriched[0]["total_score"] > 90
    assert enriched[0]["evidence_sources"] == ["official", "alumni"]
    assert enriched[0]["alumni_evidence_count"] == 3
    assert "Bo Li Lab" in enriched[0]["alumni_patterns"]
    assert enriched[0]["linkedin_backing_count"] == 3
