"""Tests for UIUC scout queue rendering."""

from __future__ import annotations

from uiuc_outputs import (
    render_alumni_collector_markdown,
    render_alumni_patterns_markdown,
    render_hidden_pathway_markdown,
    render_pathways_markdown,
    render_playbook_markdown,
    render_queue_markdown,
    render_sources_markdown,
)


def test_render_queue_markdown_includes_ranked_items() -> None:
    markdown = render_queue_markdown(
        [
            {
                "title": "Bo Li - Trustworthy AI",
                "type": "cold_outreach_target",
                "track": "ml_ai_research",
                "total_score": 81,
                "next_action": "reach_out",
                "company_archetypes": ["Anthropic"],
                "fit_reasons": ["Trustworthy AI fit"],
                "url": "https://example.com/bo-li",
            },
            {
                "title": "Machine Learning Compiler Intern",
                "type": "uiuc_technical_opening",
                "track": "ml_ai_research",
                "total_score": 88,
                "next_action": "apply_now",
                "company_archetypes": ["Nvidia", "Databricks"],
                "fit_reasons": ["ML infra fit", "Strong systems overlap"],
                "url": "https://researchpark.illinois.edu/job/ml-compiler/",
            },
        ]
    )

    assert "# UIUC Scout Queue" in markdown
    assert "1. **Machine Learning Compiler Intern**" in markdown
    assert "Next action: `apply_now`" in markdown
    assert "Mirrors: Nvidia, Databricks" in markdown
    assert "Evidence: official" in markdown
    assert "2. **Bo Li - Trustworthy AI**" in markdown


def test_render_alumni_patterns_markdown_includes_patterns() -> None:
    markdown = render_alumni_patterns_markdown(
        [
            {
                "entity_name": "NCSA SPIN",
                "entity_type": "program",
                "evidence_count": 3,
                "score": 44,
                "path_tags": ["ml_ai_research"],
                "recommended_action": "reach_out",
                "fit_reasons": ["Repeated across UIUC profiles."],
            }
        ]
    )

    assert "# UIUC Scout Alumni Patterns" in markdown
    assert "**NCSA SPIN**" in markdown
    assert "Evidence count: `3`" in markdown


def test_render_playbook_markdown_summarizes_paths() -> None:
    markdown = render_playbook_markdown(
        [
            {
                "title": "Bo Li - Trustworthy AI",
                "next_action": "reach_out",
                "track": "ml_ai_research",
                "evidence_sources": ["official", "alumni"],
            }
        ],
        [
            {
                "entity_name": "NCSA SPIN",
                "entity_type": "program",
                "evidence_count": 3,
                "path_tags": ["ml_ai_research"],
            }
        ],
        [{"name": "Alice Illinois"}],
    )

    assert "# UIUC Scout Playbook" in markdown
    assert "Profiles analyzed: `1`" in markdown
    assert "**Bo Li - Trustworthy AI**" in markdown
    assert "**NCSA SPIN**" in markdown


def test_render_sources_markdown_includes_health() -> None:
    markdown = render_sources_markdown(
        [{"entity_name": "NCSA", "entity_type": "center", "evidence_count": 2}],
        [{"source": "gies_dsrs", "status": "healthy", "records_found": 1}],
    )

    assert "# UIUC Scout Sources" in markdown
    assert "status `healthy`" in markdown
    assert "NCSA" in markdown


def test_render_alumni_collector_markdown_summarizes_provider_health() -> None:
    markdown = render_alumni_collector_markdown(
        {
            "ran_at": "2026-04-16T12:00:00+00:00",
            "mode": "hybrid",
            "queries_run": 72,
            "candidates_found": 4,
            "profiles_promoted": 2,
            "output_dir": "/tmp/alumni-auto",
            "provider_statuses": [
                {"provider": "public", "status": "blocked", "queries_run": 72, "candidates_found": 0},
                {"provider": "browser_assisted", "status": "healthy", "queries_run": 0, "candidates_found": 4},
            ],
            "errors": [{"provider": "public", "status": "blocked"}],
        }
    )

    assert "# UIUC Alumni Collector" in markdown
    assert "Mode: `hybrid`" in markdown
    assert "**public**: `blocked`" in markdown
    assert "browser_assisted" in markdown


def test_render_pathways_markdown_includes_hidden_routes() -> None:
    markdown = render_pathways_markdown(
        [
            {
                "title": "Illinois Machine Learning Seminar",
                "hidden_pathway_score": 23,
                "officiality": "official",
                "pathway_recommended_action": "reach_out",
                "description": "Seminar that repeatedly surfaces research-facing student involvement.",
                "student_access_signals": ["student", "seminar", "presenters"],
                "url": "https://publish.illinois.edu/ml-seminar/",
            }
        ]
    )

    assert "# UIUC Hidden Pathways" in markdown
    assert "**Illinois Machine Learning Seminar**" in markdown
    assert "Action: `reach_out`" in markdown


def test_render_hidden_pathway_markdown_includes_pathway_details() -> None:
    markdown = render_hidden_pathway_markdown(
        {
            "title": "NCSA SPIN",
            "officiality": "official",
            "pathway_kind": "program",
            "hidden_pathway_score": 26,
            "pathway_recommended_action": "reach_out",
            "unit": "NCSA",
            "department": "SPIN",
            "description": "Student pathway into applied ML and research software work.",
            "domain_tags": ["machine learning", "research"],
            "student_access_signals": ["student", "apply"],
            "url": "https://spin.ncsa.illinois.edu/",
        }
    )

    assert "# NCSA SPIN" in markdown
    assert "Officiality: `official`" in markdown
    assert "Student access signals: student, apply" in markdown
