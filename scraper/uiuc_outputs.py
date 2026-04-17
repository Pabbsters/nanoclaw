"""Vault-oriented renderers and writers for the UIUC scout queue."""

from __future__ import annotations

import json
import os
from pathlib import Path

from uiuc_config import UIUC_HIDDEN_PATHWAY_PAGES, UIUC_SEED_TARGETS, UIUC_SOURCE_PAGES
from uiuc_outreach import build_constant_template_markdown


def render_queue_markdown(opportunities: list[dict]) -> str:
    """Render the ranked UIUC scout queue as markdown."""
    ranked_opportunities = sorted(
        opportunities,
        key=lambda opportunity: opportunity.get("total_score", 0),
        reverse=True,
    )
    lines = [
        "# UIUC Scout Queue",
        "",
        "Ranked by fit to Ruthwik's ML/AI, technical SWE, and quant/fintech paths.",
        "",
    ]

    if not ranked_opportunities:
        lines.append("No opportunities ranked yet.")
        return "\n".join(lines)

    for index, opportunity in enumerate(ranked_opportunities, start=1):
        lines.extend(
            [
                f"{index}. **{opportunity['title']}**",
                f"Score: {opportunity['total_score']} | Track: `{opportunity['track']}` | Type: `{opportunity['type']}`",
                f"Next action: `{opportunity['next_action']}`",
                f"Mirrors: {', '.join(opportunity.get('company_archetypes', [])) or 'None yet'}",
                f"Evidence: {', '.join(opportunity.get('evidence_sources', [])) or 'official'}",
                f"Why: {opportunity.get('fit_reasons', ['No rationale yet'])[0]}",
                f"Link: {opportunity['url']}",
                "",
            ]
        )
    return "\n".join(lines).strip() + "\n"


def render_sources_markdown(alumni_patterns: list[dict] | None = None, source_health: list[dict] | None = None) -> str:
    """Render a tracked source inventory for the UIUC scout."""
    lines = [
        "# UIUC Scout Sources",
        "",
        "## Live Pages",
        "",
    ]
    for page in UIUC_SOURCE_PAGES:
        health = next((item for item in (source_health or []) if item.get("source") == page["source"]), None)
        status = health.get("status") if health else "unknown"
        records_found = health.get("records_found") if health else None
        details: list[str] = [f"status `{status}`"]
        if page.get("max_profiles"):
            details.append(f"cap {page['max_profiles']}")
        if records_found is not None:
            details.append(f"{records_found} records")
        lines.append(f"- **{page['source']}**: {page['url']} | " + " | ".join(details))

    lines.extend(["", "## Hidden Pathways Pages", ""])
    for page in UIUC_HIDDEN_PATHWAY_PAGES:
        health = next((item for item in (source_health or []) if item.get("source") == page["source"]), None)
        status = health.get("status") if health else "unknown"
        records_found = health.get("records_found") if health else None
        details = [f"status `{status}`", f"officiality `{page.get('officiality', 'official')}`"]
        if records_found is not None:
            details.append(f"{records_found} records")
        lines.append(f"- **{page['source']}**: {page['url']} | " + " | ".join(details))

    lines.extend(["", "## Curated Seed Targets", ""])
    for seed in UIUC_SEED_TARGETS:
        lines.append(f"- **{seed['title']}**: {seed['url']}")

    if alumni_patterns:
        lines.extend(["", "## Alumni-Discovered Signals", ""])
        for pattern in alumni_patterns[:10]:
            lines.append(
                f"- **{pattern['entity_name']}** (`{pattern['entity_type']}`): {pattern['evidence_count']} UIUC profiles"
            )

    return "\n".join(lines).strip() + "\n"


def render_alumni_patterns_markdown(patterns: list[dict]) -> str:
    """Render repeated alumni-derived pathways and signals."""
    lines = [
        "# UIUC Scout Alumni Patterns",
        "",
        "Repeated labs, programs, centers, and pathways found across relevant UIUC profiles.",
        "",
    ]
    if not patterns:
        lines.append("No alumni patterns captured yet.")
        return "\n".join(lines).strip() + "\n"

    for index, pattern in enumerate(patterns, start=1):
        lines.extend(
            [
                f"{index}. **{pattern['entity_name']}**",
                f"Type: `{pattern['entity_type']}` | Evidence count: `{pattern['evidence_count']}` | Score: `{pattern['score']}`",
                f"Path tags: {', '.join(pattern.get('path_tags', [])) or 'None captured'}",
                f"Recommended action: `{pattern.get('recommended_action', 'track')}`",
                f"Why: {(pattern.get('fit_reasons') or ['No rationale yet'])[0]}",
                "",
            ]
        )
    return "\n".join(lines).strip() + "\n"


def render_playbook_markdown(opportunities: list[dict], patterns: list[dict], alumni_profiles: list[dict]) -> str:
    """Render a high-level playbook describing how UIUC people got there."""
    lines = [
        "# UIUC Scout Playbook",
        "",
        "How UIUC students and alumni are reaching ML/AI, research engineering, and quant-adjacent work.",
        "",
        f"- Profiles analyzed: `{len(alumni_profiles)}`",
        f"- Alumni patterns captured: `{len(patterns)}`",
        f"- Ranked Illinois opportunities: `{len(opportunities)}`",
        "",
        "## Best Next Paths",
        "",
    ]

    for opportunity in opportunities[:8]:
        lines.extend(
            [
                f"- **{opportunity['title']}**: `{opportunity['next_action']}` because it fits `{opportunity['track']}` and is backed by {', '.join(opportunity.get('evidence_sources', [])) or 'official evidence'}.",
            ]
        )

    lines.extend(["", "## Repeated Illinois Resources", ""])
    top_resource_patterns = [
        pattern for pattern in patterns
        if pattern.get("entity_type") in {"professor", "lab", "center", "program", "resource"}
    ]
    for pattern in top_resource_patterns[:8]:
        lines.append(
            f"- **{pattern['entity_name']}**: seen in `{pattern['evidence_count']}` UIUC profiles and linked to {', '.join(pattern.get('path_tags', [])) or 'general technical'} paths."
        )

    return "\n".join(lines).strip() + "\n"


def render_pathways_markdown(hidden_pathway_records: list[dict]) -> str:
    """Render ranked hidden Illinois pathways outside the main queue."""
    lines = [
        "# UIUC Hidden Pathways",
        "",
        "Illinois-owned and clearly Illinois-affiliated routes that can lead into research, technical internships, and stronger outreach targets.",
        "",
    ]
    ranked = sorted(
        hidden_pathway_records,
        key=lambda record: int(record.get("hidden_pathway_score", 0) or 0),
        reverse=True,
    )
    if not ranked:
        lines.append("No hidden pathways captured yet.")
        return "\n".join(lines).strip() + "\n"

    for index, record in enumerate(ranked, start=1):
        lines.extend(
            [
                f"{index}. **{record.get('title', 'Unnamed pathway')}**",
                f"Score: `{record.get('hidden_pathway_score', 0)}` | Officiality: `{record.get('officiality', 'official')}` | Action: `{record.get('pathway_recommended_action', 'track')}`",
                f"Why: {record.get('description', 'No description captured')}",
                f"Signals: {', '.join(record.get('student_access_signals', [])) or 'None captured'}",
                f"Link: {record.get('url', '')}",
                "",
            ]
        )
    return "\n".join(lines).strip() + "\n"


def render_alumni_collector_markdown(summary: dict | None) -> str:
    """Render the latest alumni collector run summary."""
    lines = [
        "# UIUC Alumni Collector",
        "",
    ]
    if not summary:
        lines.append("No collector runs recorded yet.")
        return "\n".join(lines).strip() + "\n"

    lines.extend(
        [
            f"- Ran at: `{summary.get('ran_at', 'unknown')}`",
            f"- Mode: `{summary.get('mode', 'unknown')}`",
            f"- Queries run: `{summary.get('queries_run', 0)}`",
            f"- Candidates found: `{summary.get('candidates_found', 0)}`",
            f"- Profiles promoted: `{summary.get('profiles_promoted', 0)}`",
            f"- Output dir: {summary.get('output_dir', 'N/A')}",
            "",
            "## Providers",
            "",
        ]
    )
    for provider in summary.get("provider_statuses", []):
        lines.append(
            f"- **{provider.get('provider', 'unknown')}**: `{provider.get('status', 'unknown')}` | queries `{provider.get('queries_run', 0)}` | candidates `{provider.get('candidates_found', 0)}`"
        )

    if summary.get("errors"):
        lines.extend(["", "## Blocked / Failed", ""])
        for provider in summary.get("errors", []):
            lines.append(f"- {provider.get('provider', 'unknown')}: `{provider.get('status', 'unknown')}`")

    return "\n".join(lines).strip() + "\n"


def sync_uiuc_outputs(
    opportunities: list[dict],
    output_dir: str | None = None,
    alumni_patterns: list[dict] | None = None,
    alumni_profiles: list[dict] | None = None,
    source_health: list[dict] | None = None,
    collector_summary: dict | None = None,
    hidden_pathway_records: list[dict] | None = None,
) -> None:
    """Write queue and source inventory into the configured Vault output directory."""
    resolved_dir = _resolve_output_dir(output_dir)
    if resolved_dir is None:
        return

    alumni_patterns = alumni_patterns or []
    alumni_profiles = alumni_profiles or []
    hidden_pathway_records = hidden_pathway_records or []

    _ensure_structure(resolved_dir)
    (resolved_dir / "queue.md").write_text(render_queue_markdown(opportunities), encoding="utf-8")
    (resolved_dir / "sources.md").write_text(render_sources_markdown(alumni_patterns, source_health), encoding="utf-8")
    (resolved_dir / "alumni-patterns.md").write_text(render_alumni_patterns_markdown(alumni_patterns), encoding="utf-8")
    (resolved_dir / "playbook.md").write_text(render_playbook_markdown(opportunities, alumni_patterns, alumni_profiles), encoding="utf-8")
    (resolved_dir / "pathways.md").write_text(render_pathways_markdown(hidden_pathway_records), encoding="utf-8")
    (resolved_dir / "alumni-collector.md").write_text(render_alumni_collector_markdown(collector_summary), encoding="utf-8")
    (resolved_dir / "alumni_profiles_merged.json").write_text(json.dumps({"profiles": alumni_profiles}, indent=2), encoding="utf-8")
    (resolved_dir / "email-template-constant.md").write_text(
        build_constant_template_markdown(resolved_dir),
        encoding="utf-8",
    )

    for opportunity in opportunities:
        slug = _slugify(opportunity.get("title", opportunity.get("id", "opportunity")))
        dossier = render_opportunity_markdown(opportunity)
        if opportunity.get("type") == "cold_outreach_target":
            (resolved_dir / "labs" / f"{slug}.md").write_text(dossier, encoding="utf-8")
            if opportunity.get("next_action") == "reach_out":
                (resolved_dir / "outreach" / f"{slug}.md").write_text(dossier, encoding="utf-8")
        else:
            (resolved_dir / "openings" / f"{slug}.md").write_text(dossier, encoding="utf-8")

        if opportunity.get("track") == "quant_fintech":
            (resolved_dir / "quant" / f"{slug}.md").write_text(dossier, encoding="utf-8")

    for pattern in alumni_patterns:
        slug = _slugify(pattern.get("entity_name", pattern.get("id", "pattern")))
        pattern_doc = render_alumni_pattern_markdown(pattern)
        (resolved_dir / "resources" / f"{slug}.md").write_text(pattern_doc, encoding="utf-8")

    for profile in alumni_profiles:
        slug = _slugify(profile.get("name", "profile"))
        profile_doc = render_alumni_profile_markdown(profile)
        (resolved_dir / "alumni" / f"{slug}.md").write_text(profile_doc, encoding="utf-8")

    for record in hidden_pathway_records:
        slug = _slugify(record.get("title", "pathway"))
        pathway_doc = render_hidden_pathway_markdown(record)
        (resolved_dir / "pathways" / f"{slug}.md").write_text(pathway_doc, encoding="utf-8")
        (resolved_dir / "resources" / f"pathway-{slug}.md").write_text(pathway_doc, encoding="utf-8")


def write_outreach_backfill(opportunities: list[dict], output_dir: str | None = None) -> None:
    """Write only cold-outreach dossiers and the shared constant template."""
    resolved_dir = _resolve_output_dir(output_dir)
    if resolved_dir is None:
        return

    _ensure_structure(resolved_dir)
    (resolved_dir / "email-template-constant.md").write_text(
        build_constant_template_markdown(resolved_dir),
        encoding="utf-8",
    )

    for opportunity in opportunities:
        if opportunity.get("type") != "cold_outreach_target":
            continue

        slug = _slugify(opportunity.get("title", opportunity.get("id", "opportunity")))
        dossier = render_opportunity_markdown(opportunity)
        default_lab_path = resolved_dir / "labs" / f"{slug}.md"
        lab_path = Path(opportunity.get("lab_doc_path", default_lab_path)).expanduser()
        lab_path.parent.mkdir(parents=True, exist_ok=True)
        lab_path.write_text(dossier, encoding="utf-8")

        if opportunity.get("next_action") != "reach_out":
            continue

        default_outreach_path = resolved_dir / "outreach" / f"{slug}.md"
        outreach_path = Path(opportunity.get("outreach_doc_path", default_outreach_path)).expanduser()
        outreach_path.parent.mkdir(parents=True, exist_ok=True)
        outreach_path.write_text(dossier, encoding="utf-8")


def render_opportunity_markdown(opportunity: dict) -> str:
    """Render a single opportunity dossier as markdown."""
    lines = [
        f"# {opportunity['title']}",
        "",
        f"- Type: `{opportunity.get('type', 'unknown')}`",
        f"- Track: `{opportunity.get('track', 'unknown')}`",
        f"- Score: `{opportunity.get('total_score', 0)}`",
        f"- Next action: `{opportunity.get('next_action', 'track')}`",
        f"- Status: `{opportunity.get('status', 'unknown')}`",
        f"- Evidence sources: {', '.join(opportunity.get('evidence_sources', [])) or 'official'}",
        "",
        "## Why It Matches",
        "",
    ]
    for reason in opportunity.get("fit_reasons", []):
        lines.append(f"- {reason}")

    lines.extend(["", "## Mirrors", ""])
    for company in opportunity.get("company_archetypes", []):
        lines.append(f"- {company}")

    if opportunity.get("alumni_patterns"):
        lines.extend(["", "## Alumni Signals", ""])
        for pattern in opportunity.get("alumni_patterns", []):
            lines.append(f"- {pattern}")

    if opportunity.get("type") == "cold_outreach_target":
        lines.extend(
            [
                "",
                "## Email Draft",
                "",
                f"Quality: `{opportunity.get('email_quality', 'needs_review')}`",
                f"Hook source: `{opportunity.get('email_hook_source', 'tag_fallback')}`",
                f"Supporting evidence: {opportunity.get('email_supporting_evidence', 'No supporting evidence captured.')}",
                f"Skills to mention: {', '.join(opportunity.get('email_skill_alignment', [])) or 'None captured'}",
            ]
        )
        if opportunity.get("email_review_reason"):
            lines.append(f"Review note: {opportunity['email_review_reason']}")
        lines.extend(
            [
                "",
                f"Intro: {opportunity.get('email_intro', 'Draft not generated yet.')}",
                "",
                f"Custom first paragraph: {opportunity.get('email_observation_paragraph', 'Draft not generated yet.')}",
                "",
                f"Constant second paragraph: {opportunity.get('email_constant_template_ref', 'email-template-constant.md')}",
            ]
        )

    lines.extend(
        [
            "",
            "## Skills / Tags",
            "",
            f"- Skills: {', '.join(opportunity.get('skills', [])) or 'None captured'}",
            f"- Tags: {', '.join(opportunity.get('tags', [])) or 'None captured'}",
            f"- Alumni evidence count: {opportunity.get('alumni_evidence_count', 0)}",
            "",
            "## Link",
            "",
            opportunity.get("url", ""),
            "",
        ]
    )
    return "\n".join(lines).strip() + "\n"


def render_alumni_pattern_markdown(pattern: dict) -> str:
    """Render one alumni-derived pattern or resource."""
    lines = [
        f"# {pattern.get('entity_name', 'Unnamed Pattern')}",
        "",
        f"- Type: `{pattern.get('entity_type', 'resource')}`",
        f"- Evidence count: `{pattern.get('evidence_count', 0)}`",
        f"- Score: `{pattern.get('score', 0)}`",
        f"- Recommended action: `{pattern.get('recommended_action', 'track')}`",
        "",
        "## Why It Matters",
        "",
    ]
    for reason in pattern.get("fit_reasons", []):
        lines.append(f"- {reason}")

    lines.extend(["", "## Sample Profiles", ""])
    for sample in pattern.get("sample_profiles", []):
        lines.append(f"- {sample.get('name', 'Unknown')} — {sample.get('headline', 'No headline')}")

    lines.extend(["", "## Path Tags", ""])
    lines.append(f"- {', '.join(pattern.get('path_tags', [])) or 'None captured'}")
    return "\n".join(lines).strip() + "\n"


def render_alumni_profile_markdown(profile: dict) -> str:
    """Render one normalized alumni profile summary."""
    lines = [
        f"# {profile.get('name', 'Unknown UIUC Profile')}",
        "",
        f"- Headline: {profile.get('headline', 'N/A')}",
        f"- Current org: {profile.get('current_org', 'N/A')}",
        f"- Path tags: {', '.join(profile.get('path_tags', [])) or 'None captured'}",
        f"- Confidence: {profile.get('confidence', 0)}",
        "",
        "## Research Orgs",
        "",
    ]
    for org in profile.get("research_orgs", []):
        lines.append(f"- {org}")

    lines.extend(["", "## Resource Signals", ""])
    for signal in profile.get("resource_signals", []):
        lines.append(f"- {signal.get('entity_name', 'Unnamed signal')} (`{signal.get('entity_type', 'resource')}`)")

    lines.extend(["", "## Projects / Skills", ""])
    lines.append(f"- Projects: {', '.join(profile.get('projects', [])) or 'None captured'}")
    lines.append(f"- Skills: {', '.join(profile.get('skills', [])) or 'None captured'}")
    return "\n".join(lines).strip() + "\n"


def render_hidden_pathway_markdown(record: dict) -> str:
    """Render one hidden Illinois pathway dossier."""
    lines = [
        f"# {record.get('title', 'Unnamed pathway')}",
        "",
        f"- Officiality: `{record.get('officiality', 'official')}`",
        f"- Pathway kind: `{record.get('pathway_kind', 'program')}`",
        f"- Hidden-pathway score: `{record.get('hidden_pathway_score', 0)}`",
        f"- Recommended action: `{record.get('pathway_recommended_action', 'track')}`",
        f"- Unit: {record.get('unit', 'UIUC')}",
        f"- Department: {record.get('department', 'Illinois')}",
        "",
        "## Why It Matters",
        "",
        f"- {record.get('description', 'No description captured')}",
        "",
        "## Skill / Access Signals",
        "",
        f"- Tags: {', '.join(record.get('domain_tags', [])) or 'None captured'}",
        f"- Student access signals: {', '.join(record.get('student_access_signals', [])) or 'None captured'}",
        "",
        "## Link",
        "",
        record.get("url", ""),
        "",
    ]
    return "\n".join(lines).strip() + "\n"


def _resolve_output_dir(output_dir: str | None = None) -> Path | None:
    if output_dir:
        return Path(output_dir).expanduser()

    env_dir = os.environ.get("UIUC_SCOUT_OUTPUT_DIR")
    if env_dir:
        return Path(env_dir).expanduser()

    default_dir = Path.home() / "Vault" / "NanoClaw" / "uiuc-scout"
    default_parent = default_dir.parent
    if default_parent.exists():
        return default_dir
    return None


def _ensure_structure(base_dir: Path) -> None:
    base_dir.mkdir(parents=True, exist_ok=True)
    for name in ("openings", "labs", "outreach", "quant", "resources", "alumni", "pathways"):
        (base_dir / name).mkdir(parents=True, exist_ok=True)


def _slugify(value: str) -> str:
    return "".join(char.lower() if char.isalnum() else "-" for char in value).strip("-")
