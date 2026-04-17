"""Tests for UIUC outreach-draft generation."""

from __future__ import annotations

from pathlib import Path

from uiuc_outreach import (
    build_constant_template_markdown,
    build_outreach_email_fields,
    load_outreach_profile_snapshot,
)


def _career_tracks_fixture() -> str:
    return "\n".join(
        [
            "# Career Tracks",
            "",
            "**Background**: Statistics + CS @ UIUC",
            "**Last updated**: 2026-04-17",
            "",
            "## Tier 1 — Apply First",
            "",
            "| Role | Entry TC | Why You |",
            "|------|----------|---------|",
            "| **ML Engineer — Computer Vision** | $155K | CV work |",
            "| **AI Engineer / LLM Engineer** | $160K | LLM work |",
            "",
            "## Tier 2 — Strong Alternatives",
            "",
            "| Role | Entry TC | Why You |",
            "|------|----------|---------|",
            "| **Data Scientist** | $120K | Stats |",
            "| **Quantitative Analyst** | $200K | Quant |",
            "",
            "## Adjacent Skills to Add (Expand Tier 1 Surface Area)",
            "",
            "### MLOps Stack — unlocks ML Infrastructure / MLOps roles",
            "- **MLflow** — experiment tracking",
            "- **Weights & Biases (W&B)** — dashboards",
            "",
            "### AI Engineering Stack — strengthens LLM Engineer / AI Engineer roles",
            "- **LangChain** — orchestration",
            "- **LlamaIndex** — RAG",
            "- **Vector DBs** — retrieval",
            "",
            "### Cloud / DevOps Foundations — required for Solutions Architect + MLOps",
            "- **Docker** — containers",
            "- **Kubernetes** — orchestration",
            "- **Terraform** — infra as code",
            "",
            "### Skip These (Low ROI for Your Track)",
            "- ❌ Embedded systems — wrong degree",
            "- ❌ Solidity / Swift / Kotlin — off path",
            "",
        ]
    )


def test_load_outreach_profile_snapshot_parses_adjacent_skills(tmp_path: Path) -> None:
    profile_path = tmp_path / "career-tracks.md"
    profile_path.write_text(_career_tracks_fixture(), encoding="utf-8")

    snapshot = load_outreach_profile_snapshot(profile_path)

    assert snapshot.last_updated == "2026-04-17"
    assert snapshot.tier1_roles[:2] == ("ML Engineer, Computer Vision", "AI Engineer / LLM Engineer")
    assert "MLflow" in snapshot.adjacent_skills_in_progress
    assert "LangChain" in snapshot.adjacent_skills_in_progress
    assert "Docker" in snapshot.adjacent_skill_groups["Cloud / DevOps Foundations"]
    assert "Embedded systems" in snapshot.excluded_skills


def test_build_outreach_email_fields_marks_specific_official_hook_send_ready(tmp_path: Path) -> None:
    profile_path = tmp_path / "career-tracks.md"
    profile_path.write_text(_career_tracks_fixture(), encoding="utf-8")
    snapshot = load_outreach_profile_snapshot(profile_path)
    opportunity = {
        "title": "Alexander Schwing",
        "faculty_name": "Alexander Schwing",
        "description": "Research group.",
        "tags": ["computer vision", "multimodal", "generative"],
        "url": "https://ece.illinois.edu/about/directory/faculty/aschwing",
        "track": "ml_ai_research",
    }
    page_context = {
        "paragraphs": [
            "His group studies computer vision, multimodal reasoning, and generative models for structured prediction."
        ]
    }

    fields = build_outreach_email_fields(opportunity, page_context, snapshot)

    assert fields["email_quality"] == "send_ready"
    assert fields["email_hook_source"] == "official_bio"
    assert "generative models for structured prediction" in fields["email_observation_paragraph"].lower()
    assert "computer vision" in ", ".join(fields["email_skill_alignment"]).lower()
    assert "building toward LangChain".lower() in ", ".join(fields["email_skill_alignment"]).lower()


def test_build_outreach_email_fields_uses_tag_fallback_and_marks_needs_review(tmp_path: Path) -> None:
    profile_path = tmp_path / "career-tracks.md"
    profile_path.write_text(_career_tracks_fixture(), encoding="utf-8")
    snapshot = load_outreach_profile_snapshot(profile_path)
    opportunity = {
        "title": "Victor Duarte",
        "faculty_name": "Victor Duarte",
        "description": "",
        "tags": ["machine learning", "optimization", "time series"],
        "url": "https://experts.illinois.edu/en/persons/victor-duarte/",
        "track": "quant_fintech",
    }

    fields = build_outreach_email_fields(opportunity, {}, snapshot)

    assert fields["email_quality"] == "needs_review"
    assert fields["email_hook_source"] == "tag_fallback"
    assert "broad topic tags" in fields["email_review_reason"].lower()
    assert "statistics" in ", ".join(fields["email_skill_alignment"]).lower()
    assert "backtesting" in ", ".join(fields["email_skill_alignment"]).lower()


def test_build_constant_template_markdown_uses_profile_snapshot(tmp_path: Path) -> None:
    profile_path = tmp_path / "career-tracks.md"
    profile_path.write_text(_career_tracks_fixture(), encoding="utf-8")

    markdown = build_constant_template_markdown("/tmp/uiuc-scout", profile_path)

    assert "# UIUC Scout Outreach Constant Paragraph" in markdown
    assert "MLflow" in markdown
    assert "LangChain" in markdown
    assert "Profile last updated: `2026-04-17`" in markdown
    assert "email-template-constant.md" in markdown


def test_build_outreach_email_fields_filters_contact_directory_noise(tmp_path: Path) -> None:
    profile_path = tmp_path / "career-tracks.md"
    profile_path.write_text(_career_tracks_fixture(), encoding="utf-8")
    snapshot = load_outreach_profile_snapshot(profile_path)
    opportunity = {
        "title": "Bo Li",
        "faculty_name": "Bo Li",
        "description": "",
        "tags": ["trustworthy ai", "privacy", "robustness"],
        "url": "https://ece.illinois.edu/about/directory/faculty/lbo",
        "track": "ml_ai_research",
    }
    page_context = {
        "paragraphs": [
            "Nikki Slack Alumni & Donor Relations Coordinator 1070 ECE Building (217) 265-4317 nslack@illinois.edu"
        ],
        "description": "",
    }

    fields = build_outreach_email_fields(opportunity, page_context, snapshot)

    assert "nikki slack" not in fields["email_observation_paragraph"].lower()
    assert fields["email_hook_source"] == "tag_fallback"
    assert fields["email_quality"] == "needs_review"


def test_build_outreach_email_fields_filters_footer_noise(tmp_path: Path) -> None:
    profile_path = tmp_path / "career-tracks.md"
    profile_path.write_text(_career_tracks_fixture(), encoding="utf-8")
    snapshot = load_outreach_profile_snapshot(profile_path)
    opportunity = {
        "title": "Victor Duarte",
        "faculty_name": "Victor Duarte",
        "description": "",
        "tags": ["machine learning", "optimization", "time series"],
        "url": "https://experts.illinois.edu/en/persons/victor-duarte/",
        "track": "quant_fintech",
    }
    page_context = {
        "paragraphs": [
            "All content on this site: Copyright 2026 Illinois Experts. All rights are reserved, including those for text and data mining."
        ],
        "description": "",
    }

    fields = build_outreach_email_fields(opportunity, page_context, snapshot)

    assert "copyright" not in fields["email_observation_paragraph"].lower()
    assert fields["email_hook_source"] == "tag_fallback"
    assert fields["email_quality"] == "needs_review"


def test_build_outreach_email_fields_filters_css_fragment_noise(tmp_path: Path) -> None:
    profile_path = tmp_path / "career-tracks.md"
    profile_path.write_text(_career_tracks_fixture(), encoding="utf-8")
    snapshot = load_outreach_profile_snapshot(profile_path)
    opportunity = {
        "title": "Bo Li",
        "faculty_name": "Bo Li",
        "description": "",
        "tags": ["computer vision", "biomedical", "machine learning"],
        "url": "https://ece.illinois.edu/about/directory/faculty/lbo",
        "track": "ml_ai_research",
    }
    page_context = {
        "paragraphs": [
            "MC 702 .st0 { fill: #FFFFFF; } .st1 { fill: #FF5F05; }"
        ],
        "description": "",
    }

    fields = build_outreach_email_fields(opportunity, page_context, snapshot)

    assert ".st0" not in fields["email_observation_paragraph"]
    assert "fill:" not in fields["email_observation_paragraph"].lower()
    assert fields["email_hook_source"] == "tag_fallback"
    assert fields["email_quality"] == "needs_review"


def test_build_outreach_email_fields_filters_cookie_banner_noise(tmp_path: Path) -> None:
    profile_path = tmp_path / "career-tracks.md"
    profile_path.write_text(_career_tracks_fixture(), encoding="utf-8")
    snapshot = load_outreach_profile_snapshot(profile_path)
    opportunity = {
        "title": "Victor Duarte",
        "faculty_name": "Victor Duarte",
        "description": "",
        "tags": ["machine learning", "optimization", "time series"],
        "url": "https://experts.illinois.edu/en/persons/victor-duarte/",
        "track": "quant_fintech",
    }
    page_context = {
        "paragraphs": [
            "We use cookies to help provide and enhance our service and tailor content. By continuing you agree to the use of cookies."
        ],
        "description": "",
    }

    fields = build_outreach_email_fields(opportunity, page_context, snapshot)

    assert "cookies" not in fields["email_observation_paragraph"].lower()
    assert fields["email_hook_source"] == "tag_fallback"
    assert fields["email_quality"] == "needs_review"


def test_build_outreach_email_fields_adds_adjacent_mlops_skills_without_overstating(tmp_path: Path) -> None:
    profile_path = tmp_path / "career-tracks.md"
    profile_path.write_text(_career_tracks_fixture(), encoding="utf-8")
    snapshot = load_outreach_profile_snapshot(profile_path)
    opportunity = {
        "title": "ML Systems Group",
        "faculty_name": "",
        "description": "Research on machine learning pipelines, experiment tracking, and deployment systems.",
        "tags": ["machine learning", "pipeline", "deployment", "infra"],
        "url": "https://cs.illinois.edu/ml-systems",
        "track": "uiuc_technical_swe",
    }
    page_context = {
        "paragraphs": [
            "The group studies machine learning pipelines, model deployment, and experiment tracking for production systems."
        ]
    }

    fields = build_outreach_email_fields(opportunity, page_context, snapshot)
    joined_alignment = ", ".join(fields["email_skill_alignment"])

    assert fields["email_quality"] == "send_ready"
    assert "building toward MLflow" in joined_alignment
    assert "building toward Weights & Biases (W&B)" in joined_alignment
    assert "MLflow" not in [skill for skill in fields["email_skill_alignment"] if not skill.startswith("building toward")]
