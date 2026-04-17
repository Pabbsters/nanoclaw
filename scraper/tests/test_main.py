"""Tests for main.py helpers used by the UIUC outreach resend flow."""

from __future__ import annotations

from pathlib import Path

from main import _load_saved_outreach_docs, _parse_saved_outreach_doc


def test_parse_saved_outreach_doc_extracts_core_fields(tmp_path: Path) -> None:
    doc = tmp_path / "bo-li.md"
    doc.write_text(
        "\n".join(
            [
                "# Bo Li",
                "",
                "- Type: `cold_outreach_target`",
                "- Track: `ml_ai_research`",
                "- Score: `106`",
                "- Next action: `reach_out`",
                "- Status: `rolling`",
                "- Evidence sources: official, alumni",
                "",
                "## Why It Matches",
                "",
                "- Trustworthy AI fit.",
                "",
                "## Mirrors",
                "",
                "- Anthropic",
                "",
                "## Alumni Signals",
                "",
                "- Trustworthy AI Lab",
                "",
                "## Skills / Tags",
                "",
                "- Skills: machine learning, robustness",
                "- Tags: trustworthy ai, privacy",
                "- Alumni evidence count: 2",
                "",
                "## Link",
                "",
                "https://example.com/bo-li",
                "",
            ]
        ),
        encoding="utf-8",
    )

    opportunity = _parse_saved_outreach_doc(doc)

    assert opportunity is not None
    assert opportunity["id"] == "bo-li"
    assert opportunity["title"] == "Bo Li"
    assert opportunity["track"] == "ml_ai_research"
    assert opportunity["company_archetypes"] == ["Anthropic"]
    assert opportunity["evidence_sources"] == ["official", "alumni"]
    assert opportunity["alumni_patterns"] == ["Trustworthy AI Lab"]
    assert opportunity["outreach_doc_path"] == str(doc)


def test_load_saved_outreach_docs_reads_directory(tmp_path: Path) -> None:
    outreach_dir = tmp_path / "outreach"
    outreach_dir.mkdir()
    (outreach_dir / "bo-li.md").write_text(
        "\n".join(
            [
                "# Bo Li",
                "",
                "- Type: `cold_outreach_target`",
                "- Track: `ml_ai_research`",
                "- Score: `106`",
                "- Next action: `reach_out`",
                "- Status: `rolling`",
                "- Evidence sources: official",
                "",
                "## Why It Matches",
                "",
                "- Trustworthy AI fit.",
                "",
                "## Mirrors",
                "",
                "- Anthropic",
                "",
                "## Skills / Tags",
                "",
                "- Skills: machine learning",
                "- Tags: trustworthy ai",
                "- Alumni evidence count: 0",
                "",
                "## Link",
                "",
                "https://example.com/bo-li",
                "",
            ]
        ),
        encoding="utf-8",
    )

    opportunities = _load_saved_outreach_docs(tmp_path)

    assert len(opportunities) == 1
    assert opportunities[0]["title"] == "Bo Li"
    assert opportunities[0]["evidence_sources"] == ["official"]
