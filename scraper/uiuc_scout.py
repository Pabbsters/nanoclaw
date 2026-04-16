"""Normalization, filtering, and scoring for the UIUC scout pipeline."""

from __future__ import annotations

import hashlib
import re
from typing import Any

from uiuc_alumni import apply_alumni_feedback
from uiuc_config import (
    DEPRIORITIZE_KEYWORDS,
    ML_AI_KEYWORDS,
    QUANT_KEYWORDS,
    STUDENT_SIGNAL_KEYWORDS,
    TECHNICAL_SWE_KEYWORDS,
    UIUC_COMPANY_ARCHETYPES,
    UIUC_PING_SCORE_THRESHOLD,
    VAULT_PROFILE_SIGNALS,
)


def _clean_text(value: str | None) -> str:
    return re.sub(r"\s+", " ", (value or "")).strip()


def _slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def _keyword_pattern(keyword: str) -> re.Pattern[str]:
    escaped = re.escape(keyword.strip().lower())
    escaped = escaped.replace(r"\ ", r"[\s\-]+")
    return re.compile(rf"(?<![a-z0-9]){escaped}(?![a-z0-9])", re.IGNORECASE)


def _contains_keyword(text: str, keyword: str) -> bool:
    return bool(_keyword_pattern(keyword).search(text))


def _combined_text(record: dict[str, Any]) -> str:
    parts = [
        record.get("title", ""),
        record.get("description", ""),
        record.get("unit", ""),
        record.get("department", ""),
        record.get("faculty", ""),
        " ".join(record.get("domain_tags", []) or []),
    ]
    return _clean_text(" ".join(parts)).lower()


def _matched_keywords(text: str, keywords: tuple[str, ...]) -> list[str]:
    return [keyword for keyword in keywords if _contains_keyword(text, keyword)]


def _infer_track(text: str) -> str | None:
    quant_matches = _matched_keywords(text, QUANT_KEYWORDS)
    ml_matches = _matched_keywords(text, ML_AI_KEYWORDS)
    tech_matches = _matched_keywords(text, TECHNICAL_SWE_KEYWORDS)

    if quant_matches:
        return "quant_fintech"
    if ml_matches:
        return "ml_ai_research"
    if tech_matches:
        return "uiuc_technical_swe"
    return None


def _entity_type(record: dict[str, Any], track: str, text: str) -> str:
    kind = record.get("entity_kind", "")
    status_hint = str(record.get("status_hint", "")).lower()

    if kind == "job_posting":
        return "uiuc_technical_opening"
    if kind in {"faculty_profile", "research_group", "lab_profile"}:
        return "cold_outreach_target"
    if "research" in kind or "research" in text:
        if "open" in status_hint or "rolling" in status_hint or "intern" in text:
            return "research_opening"
        return "cold_outreach_target"
    return "uiuc_technical_opening"


def _status(record: dict[str, Any], text: str) -> str:
    status_hint = str(record.get("status_hint", "")).lower()
    if "closed" in status_hint:
        return "closed_but_outreachable"
    if "open" in status_hint:
        return "open"
    if "rolling" in status_hint:
        return "rolling"
    if "intern" in text or "apply" in text or "opportunity" in text:
        return "open"
    return "unknown"


def _company_archetypes(text: str) -> list[str]:
    matches: list[str] = []
    for keyword, companies in UIUC_COMPANY_ARCHETYPES.items():
        if _contains_keyword(text, keyword):
            matches.extend(companies)
    if not matches and "ml_ai_research" in text:
        matches.extend(("Anthropic", "OpenAI"))
    # Preserve order while removing duplicates.
    seen: set[str] = set()
    ordered: list[str] = []
    for company in matches:
        if company not in seen:
            seen.add(company)
            ordered.append(company)
    return ordered


def _fit_reasons(track: str, text: str, company_archetypes: list[str]) -> list[str]:
    reasons = list(VAULT_PROFILE_SIGNALS.get(track, ()))

    if "trustworthy ai" in text:
        reasons.append("Trustworthy AI focus lines up with your saved Bo Li target and AI safety-leaning interests.")
    if "nlp" in text or "knowledge graph" in text:
        reasons.append("NLP and knowledge-graph work fits your Heng Ji / language-tech direction.")
    if "computer vision" in text or "vision" in text:
        reasons.append("Computer vision work builds directly on your CV projects and hackathon win.")
    if track == "quant_fintech":
        reasons.append("Quant / fintech work connects directly to your backtesting platform and stats-heavy path.")
    if company_archetypes:
        reasons.append(f"This resembles work patterns at {', '.join(company_archetypes[:3])}.")

    seen: set[str] = set()
    ordered: list[str] = []
    for reason in reasons:
        if reason not in seen:
            seen.add(reason)
            ordered.append(reason)
    return ordered


def _score_components(record: dict[str, Any], track: str, text: str, company_archetypes: list[str]) -> dict[str, int]:
    entity_kind = str(record.get("entity_kind", "")).lower()
    status = _status(record, text)

    path_fit = 20 if track == "ml_ai_research" else 18 if track == "quant_fintech" else 13
    skill_growth_fit = min(20, 10 + len(_matched_keywords(text, ML_AI_KEYWORDS if track == "ml_ai_research" else QUANT_KEYWORDS if track == "quant_fintech" else TECHNICAL_SWE_KEYWORDS)) * 3)
    evidence_fit = 16 if track == "quant_fintech" else 15 if track == "ml_ai_research" else 12
    work_shape_similarity = min(15, 7 + len(company_archetypes) * 2)
    uiuc_relevance = 10 if "illinois" in text or "uiuc" in text or "ncsa" in text else 7
    student_accessibility = 10 if any(keyword in text for keyword in STUDENT_SIGNAL_KEYWORDS) or entity_kind in {"faculty_profile", "research_group", "lab_profile"} else 5
    actionability = {
        "open": 10,
        "rolling": 8,
        "unknown": 6,
        "closed_but_outreachable": 4,
    }[status]
    freshness = 7 if record.get("last_seen") else 4

    components = {
        "path_fit": path_fit,
        "skill_growth_fit": skill_growth_fit,
        "evidence_fit": evidence_fit,
        "work_shape_similarity": work_shape_similarity,
        "uiuc_relevance": uiuc_relevance,
        "student_accessibility": student_accessibility,
        "actionability": actionability,
        "freshness": freshness,
    }
    if record.get("hidden_pathway_signal"):
        officiality = str(record.get("officiality", "official"))
        student_access_signals = list(record.get("student_access_signals", []))
        components["pathway_leverage"] = min(12, 4 + len(student_access_signals) + len(company_archetypes))
        components["hidden_route_value"] = min(
            10,
            4 + len(_matched_keywords(text, ML_AI_KEYWORDS if track == "ml_ai_research" else QUANT_KEYWORDS if track == "quant_fintech" else TECHNICAL_SWE_KEYWORDS)),
        )
        components["officiality"] = 8 if officiality == "official" else 5
        components["repeat_signal_strength"] = int(record.get("pathway_repeat_signal", 1) or 1)
        components["conversion_potential"] = min(
            10,
            3 + len(student_access_signals) + (2 if any(_contains_keyword(text, token) for token in ("join", "apply", "contact")) else 0),
        )
    return components


def _next_action(opportunity_type: str, total_score: int, status: str, text: str, evidence_sources: list[str]) -> str:
    if opportunity_type == "cold_outreach_target":
        return "reach_out" if total_score >= 60 else "track"
    has_official_evidence = "official" in evidence_sources
    has_explicit_apply_signal = any(
        keyword in text
        for keyword in ("apply", "application", "intern", "internship", "job", "position", "opening", "fellowship", "reu", "spin")
    )
    if status in {"open", "rolling"} and total_score >= 60 and has_official_evidence and has_explicit_apply_signal:
        return "apply_now"
    if status == "closed_but_outreachable" and total_score >= 68:
        return "reach_out"
    if total_score >= 68 and not has_official_evidence:
        return "reach_out"
    return "track"


def normalize_source_record(record: dict[str, Any]) -> dict[str, Any] | None:
    """Normalize a raw UIUC record into a scored opportunity."""
    text = _combined_text(record)
    if not text:
        return None

    if any(_contains_keyword(text, keyword) for keyword in DEPRIORITIZE_KEYWORDS):
        return None

    track = _infer_track(text)
    if track is None:
        return None

    opportunity_type = _entity_type(record, track, text)
    status = _status(record, text)
    company_archetypes = _company_archetypes(text)
    score_components = _score_components(record, track, text, company_archetypes)
    total_score = sum(score_components.values())
    if record.get("hidden_pathway_signal") and total_score < 72:
        return None
    evidence_sources = list(record.get("evidence_sources", ["official" if str(record.get("source", "")).startswith("uiuc_alumni") is False else "alumni"]))
    next_action = _next_action(opportunity_type, total_score, status, text, evidence_sources)
    title = _clean_text(str(record.get("title", "")))
    url = _clean_text(str(record.get("url", "")))
    faculty_name = _clean_text(str(record.get("faculty", "")))
    department = _clean_text(str(record.get("department", "")))
    lab = title if opportunity_type == "cold_outreach_target" else ""
    fit_reasons = _fit_reasons(track, text, company_archetypes)
    tags = sorted(
        {
            *(_matched_keywords(text, ML_AI_KEYWORDS)),
            *(_matched_keywords(text, QUANT_KEYWORDS)),
            *(_matched_keywords(text, TECHNICAL_SWE_KEYWORDS)),
            *[str(tag).lower() for tag in record.get("domain_tags", []) or []],
        }
    )
    skills = [
        tag for tag in tags
        if tag in {"python", "machine learning", "ml systems", "nlp", "computer vision", "time series", "optimization", "search", "compiler", "data"}
    ]
    opportunity_id = _slugify(title or url) or hashlib.sha256(url.encode()).hexdigest()[:16]

    return {
        "source": str(record.get("source", "uiuc_scout")),
        "id": opportunity_id,
        "title": title,
        "url": url,
        "type": opportunity_type,
        "track": track,
        "org": _clean_text(str(record.get("unit", ""))) or "UIUC",
        "department": department,
        "lab": lab,
        "faculty_name": faculty_name,
        "status": status,
        "next_action": next_action,
        "total_score": total_score,
        "company_archetypes": company_archetypes,
        "skills": skills,
        "tags": tags,
        "fit_reasons": fit_reasons,
        "score_components": score_components,
        "contact_info": {
            "email": _clean_text(str(record.get("contact", ""))),
            "url": url,
        },
        "description": _clean_text(str(record.get("description", ""))),
        "evidence_sources": evidence_sources,
        "alumni_patterns": list(record.get("alumni_patterns", [])),
        "alumni_evidence_count": int(record.get("alumni_evidence_count", 0) or 0),
        "hidden_pathway_signals": list(record.get("hidden_pathway_signals", [])),
        "should_ping": total_score >= UIUC_PING_SCORE_THRESHOLD and next_action in {"apply_now", "reach_out"},
    }


def dedupe_opportunities(opportunities: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deduplicate opportunities by canonical URL or title, keeping the highest score."""
    deduped: dict[str, dict[str, Any]] = {}
    for opportunity in opportunities:
        key = opportunity.get("url") or opportunity.get("title") or opportunity.get("id")
        existing = deduped.get(key)
        if existing is None or opportunity.get("total_score", 0) > existing.get("total_score", 0):
            deduped[key] = opportunity
    return sorted(deduped.values(), key=lambda item: item.get("total_score", 0), reverse=True)


def _opportunity_text(opportunity: dict[str, Any]) -> str:
    return _clean_text(
        " ".join(
            [
                str(opportunity.get("title", "")),
                str(opportunity.get("org", "")),
                str(opportunity.get("department", "")),
                str(opportunity.get("lab", "")),
                str(opportunity.get("faculty_name", "")),
                " ".join(opportunity.get("tags", []) or []),
                str(opportunity.get("description", "")),
            ]
        )
    ).lower()


def _hidden_pathway_matches_opportunity(opportunity: dict[str, Any], record: dict[str, Any]) -> bool:
    pathway_title = _clean_text(str(record.get("title", ""))).lower()
    pathway_department = _clean_text(str(record.get("department", ""))).lower()
    opportunity_text = _opportunity_text(opportunity)
    if not pathway_title:
        return False
    if _contains_keyword(opportunity_text, pathway_title):
        return True
    return bool(pathway_department and _contains_keyword(opportunity_text, pathway_department))


def apply_hidden_pathway_feedback(opportunities: list[dict[str, Any]], hidden_pathway_records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Boost opportunities using hidden-pathway signals without changing ping rules."""
    enriched: list[dict[str, Any]] = []
    for opportunity in opportunities:
        matched_records = [
            record for record in hidden_pathway_records
            if _hidden_pathway_matches_opportunity(opportunity, record)
        ]
        score_components = dict(opportunity.get("score_components", {}))
        if matched_records:
            score_components["repeat_signal_strength"] = max(
                int(score_components.get("repeat_signal_strength", 0) or 0),
                min(10, len(matched_records) * 3),
            )
            score_components["pathway_leverage"] = max(
                int(score_components.get("pathway_leverage", 0) or 0),
                min(12, max(int(record.get("hidden_pathway_score", 0) or 0) // 2 for record in matched_records)),
            )
            score_components["officiality"] = max(
                int(score_components.get("officiality", 0) or 0),
                max(8 if str(record.get("officiality", "official")) == "official" else 5 for record in matched_records),
            )
            score_components["conversion_potential"] = max(
                int(score_components.get("conversion_potential", 0) or 0),
                min(10, sum(len(record.get("student_access_signals", [])) for record in matched_records)),
            )

        fit_reasons = list(opportunity.get("fit_reasons", []))
        if matched_records:
            fit_reasons.append(
                f"Supported by Illinois pathway signals via {', '.join(record['title'] for record in matched_records[:3])}."
            )

        updated = {
            **opportunity,
            "score_components": score_components,
            "total_score": sum(score_components.values()),
            "fit_reasons": list(dict.fromkeys(fit_reasons)),
            "evidence_sources": list(dict.fromkeys([*(opportunity.get("evidence_sources") or ["official"]), *(["hidden_pathways"] if matched_records else [])])),
            "hidden_pathway_signals": [record["title"] for record in matched_records],
        }
        updated["should_ping"] = (
            updated["total_score"] >= UIUC_PING_SCORE_THRESHOLD
            and updated.get("next_action") in {"apply_now", "reach_out"}
        )
        enriched.append(updated)

    return sorted(enriched, key=lambda item: item.get("total_score", 0), reverse=True)


def build_opportunities(
    records: list[dict[str, Any]],
    alumni_patterns: list[dict[str, Any]] | None = None,
    hidden_pathway_records: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Normalize, filter, sort, and enrich UIUC records."""
    normalized = [normalize_source_record(record) for record in records]
    kept = [opportunity for opportunity in normalized if opportunity is not None]
    deduped = dedupe_opportunities(kept)
    alumni_enriched = apply_alumni_feedback(deduped, alumni_patterns or [])
    return apply_hidden_pathway_feedback(alumni_enriched, hidden_pathway_records or [])


def select_ping_candidates(opportunities: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    """Choose the strongest ping-worthy opportunities for this run."""
    pingable = [item for item in opportunities if item.get("should_ping")]
    pingable.sort(key=lambda item: item.get("total_score", 0), reverse=True)
    return pingable[:limit]
