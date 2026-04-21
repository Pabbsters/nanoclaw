"""LinkedIn/Composio-assisted alumni intelligence for the UIUC scout."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from uiuc_config import ML_AI_KEYWORDS, QUANT_KEYWORDS, TECHNICAL_SWE_KEYWORDS, VAULT_PROFILE_SIGNALS


UIUC_EDUCATION_KEYWORDS: tuple[str, ...] = (
    "university of illinois urbana-champaign",
    "university of illinois at urbana champaign",
    "uiuc",
    "urbana-champaign",
    "grainger college of engineering",
    "gies college of business",
)

ILLINOIS_RESOURCE_KEYWORDS: tuple[str, ...] = (
    "uiuc",
    "illinois",
    "ncsa",
    "research park",
    "grainger",
    "gies",
    "carle illinois",
    "igb",
    "ischool",
    "electrical and computer engineering",
    "bioengineering",
    "statistics",
    "computer science",
)

GENERIC_PATTERN_NAMES: tuple[str, ...] = (
    "university of illinois",
    "uiuc",
    "linkedin",
    "machine learning",
    "artificial intelligence",
    "computer science",
    "statistics",
)

PATH_TAG_KEYWORDS: dict[str, tuple[str, ...]] = {
    "ml_ai_research": ML_AI_KEYWORDS + ("agentic ai", "research assistant", "research engineer"),
    "uiuc_technical_swe": TECHNICAL_SWE_KEYWORDS + ("research software", "student developer"),
    "quant_fintech": QUANT_KEYWORDS + ("quant researcher", "quant developer"),
}

EVIDENCE_PROVIDER_STRENGTH: dict[str, int] = {
    "browser_assisted_linkedin": 3,
    "public_linkedin": 2,
    "fallback_public": 1,
}


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


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        parts = re.split(r"[|\n;]", value)
        return [_clean_text(part) for part in parts if _clean_text(part)]
    if isinstance(value, list):
        flattened: list[str] = []
        for item in value:
            if isinstance(item, dict):
                candidate = (
                    item.get("name")
                    or item.get("title")
                    or item.get("entity_name")
                    or item.get("organization")
                )
                if candidate:
                    flattened.append(_clean_text(str(candidate)))
            else:
                flattened.extend(_string_list(item))
        return [item for item in flattened if item]
    return [_clean_text(str(value))]


def _matched_keywords(text: str, keywords: tuple[str, ...]) -> list[str]:
    return [keyword for keyword in keywords if _contains_keyword(text, keyword)]


def _canonical_evidence_provider(record: dict[str, Any], profile_url: str) -> str:
    source = _clean_text(str(record.get("source") or "")).lower()
    url = profile_url.lower()
    if any(token in source for token in ("browser_assisted", "composio", "signed_in", "linkedin_export")):
        return "browser_assisted_linkedin"
    if "linkedin" in source or "linkedin.com/in" in url:
        return "public_linkedin"
    return "fallback_public"


def _infer_path_tags(text: str) -> list[str]:
    matched: list[str] = []
    for path_tag, keywords in PATH_TAG_KEYWORDS.items():
        if any(_contains_keyword(text, keyword) for keyword in keywords):
            matched.append(path_tag)
    return matched


def _infer_entity_type(name: str) -> str:
    lowered = name.lower()
    if "professor" in lowered or lowered.startswith("dr. "):
        return "professor"
    if "lab" in lowered or "laboratory" in lowered:
        return "lab"
    if "center" in lowered or "centre" in lowered or "institute" in lowered:
        return "center"
    if "program" in lowered or "fellowship" in lowered or "reu" in lowered or "srop" in lowered:
        return "program"
    if "club" in lowered or "society" in lowered:
        return "resource"
    return "resource"


def _entity_type_rank(entity_type: str) -> int:
    return {
        "professor": 6,
        "lab": 5,
        "center": 4,
        "program": 3,
        "resource": 2,
        "employer": 1,
    }.get(entity_type, 0)


def _is_illinois_connected(value: str) -> bool:
    lowered = value.lower()
    return any(_contains_keyword(lowered, keyword) for keyword in ILLINOIS_RESOURCE_KEYWORDS)


def _normalize_resource_signal(signal: Any) -> dict[str, Any] | None:
    if isinstance(signal, dict):
        name = _clean_text(
            str(
                signal.get("entity_name")
                or signal.get("name")
                or signal.get("title")
                or signal.get("organization")
                or ""
            )
        )
        entity_type = _clean_text(str(signal.get("entity_type") or signal.get("type") or signal.get("kind") or ""))
        url = _clean_text(str(signal.get("url") or ""))
        path_tags = _string_list(signal.get("path_tags"))
        description = _clean_text(str(signal.get("description") or ""))
    else:
        name = _clean_text(str(signal))
        entity_type = ""
        url = ""
        path_tags = []
        description = ""

    if not name:
        return None

    resolved_type = entity_type.lower() or _infer_entity_type(name)
    inferred_tags = _infer_path_tags(f"{name} {description}".lower())

    return {
        "entity_name": name,
        "entity_type": resolved_type,
        "url": url,
        "path_tags": sorted({*path_tags, *inferred_tags}),
        "description": description,
    }


def _default_alumni_data_paths() -> list[Path]:
    base_dir = Path(__file__).resolve().parent
    return [
        base_dir / "data" / "uiuc_alumni_seed.json",
        Path("~/Vault/NanoClaw/uiuc-scout/alumni_profiles.json").expanduser(),
        Path("~/Vault/NanoClaw/uiuc-scout/alumni_profiles_merged.json").expanduser(),
        Path("~/Vault/NanoClaw/uiuc-scout/input/alumni_profiles.json").expanduser(),
        Path("~/Vault/NanoClaw/uiuc-scout/input").expanduser(),
        Path("~/Vault/NanoClaw/uiuc-scout/input/alumni-auto").expanduser(),
    ]


def _expand_candidate_path(path: Path) -> list[Path]:
    if path.is_dir():
        return sorted(item for item in path.glob("*.json") if item.is_file())
    return [path]


def _load_profile_payload(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        items = payload.get("profiles") or payload.get("items") or payload.get("records") or []
    elif isinstance(payload, list):
        items = payload
    else:
        items = []
    return [dict(item) for item in items if isinstance(item, dict)]


def load_alumni_profile_records(data_path: str | None = None) -> list[dict[str, Any]]:
    """Load LinkedIn/Composio exported alumni records from local JSON sources."""
    if data_path:
        candidate_paths = [Path(data_path).expanduser()]
    else:
        candidate_paths = [
            Path(path).expanduser()
            for path in (
                os.environ.get("UIUC_SCOUT_ALUMNI_DATA_PATH"),
                os.environ.get("COMPOSIO_UIUC_ALUMNI_EXPORT_PATH"),
                os.environ.get("UIUC_SCOUT_ALUMNI_DATA_DIR"),
            )
            if path
        ]
        candidate_paths.extend(_default_alumni_data_paths())

    seen: set[tuple[str, str]] = set()
    records: list[dict[str, Any]] = []
    expanded_candidates: list[Path] = []
    for path in candidate_paths:
        if not path.exists():
            continue
        expanded_candidates.extend(_expand_candidate_path(path))

    for path in expanded_candidates:
        for item in _load_profile_payload(path):
            key = (
                _clean_text(str(item.get("profile_url") or item.get("url") or "")).lower(),
                _clean_text(str(item.get("name") or item.get("full_name") or "")).lower(),
            )
            if key in seen:
                continue
            seen.add(key)
            records.append(item)
    return records


def normalize_linkedin_profile_record(record: dict[str, Any]) -> dict[str, Any] | None:
    """Normalize a raw LinkedIn-style profile into a scout-ready alumni record."""
    profile_url = _clean_text(str(record.get("profile_url") or record.get("url") or ""))
    name = _clean_text(str(record.get("name") or record.get("full_name") or ""))
    headline = _clean_text(str(record.get("headline") or record.get("summary") or ""))
    current_org = _clean_text(str(record.get("current_org") or record.get("current_company") or ""))
    past_orgs = _string_list(record.get("past_orgs") or record.get("past_companies"))
    research_orgs = _string_list(record.get("research_orgs") or record.get("labs") or record.get("groups"))
    projects = _string_list(record.get("projects"))
    skills = _string_list(record.get("skills"))

    education_entries = _string_list(record.get("education")) + _string_list(record.get("schools")) + _string_list(record.get("school"))
    education_text = " ".join(education_entries).lower()
    explicit_uiuc_match = bool(record.get("education_matches_uiuc"))
    education_matches_uiuc = explicit_uiuc_match or any(
        _contains_keyword(education_text, keyword) for keyword in UIUC_EDUCATION_KEYWORDS
    )
    if not education_matches_uiuc:
        return None

    resource_signals = [
        normalized
        for normalized in (
            _normalize_resource_signal(signal)
            for signal in (record.get("resource_signals") or record.get("resources") or [])
        )
        if normalized is not None
    ]

    combined_text = " ".join(
        [
            name,
            headline,
            current_org,
            " ".join(past_orgs),
            " ".join(research_orgs),
            " ".join(projects),
            " ".join(skills),
            " ".join(signal["entity_name"] for signal in resource_signals),
        ]
    ).lower()
    path_tags = sorted({*(_string_list(record.get("path_tags"))), *_infer_path_tags(combined_text)})

    if not path_tags and not any(_is_illinois_connected(item) for item in [current_org, *past_orgs, *research_orgs]):
        return None

    evidence_provider = _canonical_evidence_provider(record, profile_url)
    source_strength = EVIDENCE_PROVIDER_STRENGTH[evidence_provider]
    confidence = float(record.get("confidence") or 0.0)
    if confidence <= 0:
        confidence = min(
            0.99,
            0.45
            + (0.2 if path_tags else 0.0)
            + (0.15 if research_orgs else 0.0)
            + (0.1 if resource_signals else 0.0),
        )
    if evidence_provider == "browser_assisted_linkedin":
        confidence = min(0.99, confidence + 0.05)

    return {
        "source": str(record.get("source") or "linkedin_assisted"),
        "profile_url": profile_url,
        "name": name or "Unknown UIUC profile",
        "headline": headline,
        "education_matches_uiuc": True,
        "current_org": current_org,
        "past_orgs": past_orgs,
        "research_orgs": research_orgs,
        "projects": projects,
        "skills": skills,
        "resource_signals": resource_signals,
        "path_tags": path_tags,
        "evidence_provider": evidence_provider,
        "source_strength": source_strength,
        "confidence": round(confidence, 2),
    }


def build_alumni_patterns(profiles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Aggregate repeated labs/resources/pathways from normalized alumni profiles."""
    aggregates: dict[str, dict[str, Any]] = {}

    for profile in profiles:
        profile_ref = {
            "name": profile.get("name", "Unknown UIUC profile"),
            "profile_url": profile.get("profile_url", ""),
            "headline": profile.get("headline", ""),
        }
        profile_tags = set(profile.get("path_tags", []))
        evidence_provider = str(profile.get("evidence_provider", "public_linkedin") or "public_linkedin")
        source_strength = int(profile.get("source_strength", EVIDENCE_PROVIDER_STRENGTH.get(evidence_provider, 1)) or 1)

        signals: list[dict[str, Any]] = []
        signals.extend(profile.get("resource_signals", []))
        signals.extend(
            _normalize_resource_signal({"name": item, "entity_type": "lab"})
            for item in profile.get("research_orgs", [])
        )
        signals.extend(
            _normalize_resource_signal({"name": item, "entity_type": "employer"})
            for item in [profile.get("current_org", ""), *profile.get("past_orgs", [])]
            if item
        )

        for signal in signals:
            if signal is None:
                continue

            entity_name = _clean_text(signal.get("entity_name", ""))
            if not entity_name:
                continue
            if any(_contains_keyword(entity_name.lower(), generic) for generic in GENERIC_PATTERN_NAMES):
                continue

            entity_type = _clean_text(signal.get("entity_type", "")) or _infer_entity_type(entity_name)
            path_tags = sorted({*profile_tags, *signal.get("path_tags", [])})
            key = _slugify(entity_name)
            aggregate = aggregates.setdefault(
                key,
                {
                    "id": f"{entity_type}:{key}",
                    "entity_type": entity_type,
                    "entity_name": entity_name,
                    "entity_url": signal.get("url", ""),
                    "evidence_count": 0,
                    "sample_profiles": [],
                    "path_tags": set(),
                    "fit_reasons": [],
                    "recommended_action": "track",
                    "score": 0,
                    "illinois_connected": _is_illinois_connected(entity_name),
                    "provider_counts": {},
                    "weighted_evidence": 0,
                    "linkedin_backing_count": 0,
                },
            )

            if not any(sample["profile_url"] == profile_ref["profile_url"] and sample["name"] == profile_ref["name"] for sample in aggregate["sample_profiles"]):
                aggregate["sample_profiles"].append(profile_ref)
                aggregate["evidence_count"] += 1
                aggregate["weighted_evidence"] += source_strength
                aggregate["provider_counts"][evidence_provider] = int(aggregate["provider_counts"].get(evidence_provider, 0) or 0) + 1
                if evidence_provider in {"browser_assisted_linkedin", "public_linkedin"}:
                    aggregate["linkedin_backing_count"] += 1

            if _entity_type_rank(entity_type) > _entity_type_rank(aggregate["entity_type"]):
                aggregate["entity_type"] = entity_type
                aggregate["id"] = f"{entity_type}:{key}"
            aggregate["path_tags"].update(path_tags)
            if signal.get("url") and not aggregate["entity_url"]:
                aggregate["entity_url"] = signal["url"]

    patterns: list[dict[str, Any]] = []
    for aggregate in aggregates.values():
        path_tags = sorted(aggregate["path_tags"])
        provider_counts = dict(aggregate["provider_counts"])
        fallback_evidence_count = sum(
            count for provider, count in provider_counts.items()
            if provider == "fallback_public"
        )
        score = aggregate["evidence_count"] * 10 + min(12, len(path_tags) * 4)
        if aggregate["entity_type"] in {"professor", "lab", "center", "program", "resource"}:
            score += 6
        if aggregate["illinois_connected"]:
            score += 8
        score += min(12, int(aggregate["weighted_evidence"]))
        if aggregate["linkedin_backing_count"]:
            score += min(8, aggregate["linkedin_backing_count"] * 2)

        fit_reasons: list[str] = []
        if aggregate["illinois_connected"]:
            fit_reasons.append(f"Repeated across UIUC profiles as an Illinois resource or stepping stone ({aggregate['evidence_count']} profiles).")
        if aggregate["linkedin_backing_count"]:
            fit_reasons.append(
                f"LinkedIn-backed across {aggregate['linkedin_backing_count']} UIUC profiles, so this looks like a real observed path rather than a weak web-only signal."
            )
        elif fallback_evidence_count:
            fit_reasons.append(
                f"Supported by fallback public evidence across {fallback_evidence_count} UIUC-linked profiles/resources while LinkedIn evidence is limited."
            )
        if "ml_ai_research" in path_tags:
            fit_reasons.extend(VAULT_PROFILE_SIGNALS["ml_ai_research"][:1])
        if "quant_fintech" in path_tags:
            fit_reasons.extend(VAULT_PROFILE_SIGNALS["quant_fintech"][:1])
        if "uiuc_technical_swe" in path_tags:
            fit_reasons.extend(VAULT_PROFILE_SIGNALS["uiuc_technical_swe"][:1])

        recommended_action = "track"
        if aggregate["illinois_connected"] and aggregate["entity_type"] in {"professor", "lab", "center", "program", "resource"} and score >= 28:
            recommended_action = "reach_out"

        patterns.append(
            {
                "id": aggregate["id"],
                "entity_type": aggregate["entity_type"],
                "entity_name": aggregate["entity_name"],
                "entity_url": aggregate["entity_url"],
                "evidence_count": aggregate["evidence_count"],
                "sample_profiles": aggregate["sample_profiles"][:5],
                "path_tags": path_tags,
                "fit_reasons": fit_reasons,
                "recommended_action": recommended_action,
                "score": score,
                "illinois_connected": aggregate["illinois_connected"],
                "evidence_providers": sorted(provider_counts),
                "provider_counts": provider_counts,
                "linkedin_backing_count": aggregate["linkedin_backing_count"],
                "fallback_evidence_count": fallback_evidence_count,
                "source_strength": aggregate["weighted_evidence"],
            }
        )

    patterns.sort(key=lambda item: (item["score"], item["evidence_count"]), reverse=True)
    return patterns


def build_source_records_from_alumni_patterns(patterns: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Turn strong Illinois alumni patterns into source-like records for the scout."""
    derived_records: list[dict[str, Any]] = []

    kind_map = {
        "professor": "faculty_profile",
        "lab": "research_group",
        "center": "research_group",
        "program": "research_program",
        "resource": "research_program",
        "employer": "research_group",
    }

    for pattern in patterns:
        if not pattern.get("illinois_connected"):
            continue
        if pattern.get("evidence_count", 0) < 2:
            continue

        entity_name = pattern["entity_name"]
        description = (
            f"Alumni-backed Illinois pathway seen across {pattern['evidence_count']} UIUC LinkedIn-style profiles. "
            f"Paths: {', '.join(pattern.get('path_tags', [])) or 'unknown'}."
        )
        derived_records.append(
            {
                "source": "uiuc_alumni_pattern",
                "url": pattern.get("entity_url") or "",
                "entity_kind": kind_map.get(pattern.get("entity_type", ""), "research_group"),
                "title": entity_name,
                "unit": "UIUC" if _is_illinois_connected(entity_name) else "Alumni Intel",
                "department": "Alumni Intel",
                "faculty": entity_name if pattern.get("entity_type") == "professor" else "",
                "description": description,
                "contact": "",
                "last_seen": "2026-04-16",
                "status_hint": "unknown",
                "domain_tags": pattern.get("path_tags", []),
                "alumni_evidence_count": pattern.get("evidence_count", 0),
                "alumni_patterns": [entity_name],
                "evidence_sources": ["alumni"],
                "alumni_evidence_providers": pattern.get("evidence_providers", []),
                "alumni_source_strength": int(pattern.get("source_strength", 0) or 0),
                "linkedin_backing_count": int(pattern.get("linkedin_backing_count", 0) or 0),
            }
        )

    return derived_records


def _opportunity_text(opportunity: dict[str, Any]) -> str:
    return _clean_text(
        " ".join(
            [
                opportunity.get("title", ""),
                opportunity.get("org", ""),
                opportunity.get("department", ""),
                opportunity.get("lab", ""),
                opportunity.get("faculty_name", ""),
                " ".join(opportunity.get("tags", []) or []),
                opportunity.get("description", ""),
            ]
        )
    ).lower()


def _pattern_matches_opportunity(opportunity: dict[str, Any], pattern: dict[str, Any]) -> bool:
    opportunity_text = _opportunity_text(opportunity)
    pattern_name = _clean_text(pattern.get("entity_name", "")).lower()
    if not pattern_name:
        return False

    if _contains_keyword(opportunity_text, pattern_name):
        return True

    aliases = [
        opportunity.get("title", ""),
        opportunity.get("org", ""),
        opportunity.get("department", ""),
        opportunity.get("faculty_name", ""),
        opportunity.get("lab", ""),
    ]
    return any(alias and _contains_keyword(pattern_name, alias.lower()) for alias in aliases)


def _vault_alignment_score(opportunity: dict[str, Any]) -> int:
    text = _opportunity_text(opportunity)
    score = 0
    for keyword in (
        "bo li",
        "heng ji",
        "victor duarte",
        "trustworthy ai",
        "knowledge graph",
        "computer vision",
        "time series",
        "optimization",
        "research engineer",
        "ncsa",
        "research park",
        "agentic ai",
    ):
        if _contains_keyword(text, keyword):
            score += 2
    return min(12, score)


def apply_alumni_feedback(opportunities: list[dict[str, Any]], patterns: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Boost and annotate opportunities using alumni-derived evidence."""
    enriched: list[dict[str, Any]] = []

    for opportunity in opportunities:
        matched_patterns = [pattern for pattern in patterns if _pattern_matches_opportunity(opportunity, pattern)]
        alumni_evidence_count = sum(pattern.get("evidence_count", 0) for pattern in matched_patterns)
        matched_path_tags = {tag for pattern in matched_patterns for tag in pattern.get("path_tags", [])}
        matched_provider_counts: dict[str, int] = {}
        linkedin_backing_count = 0
        alumni_source_strength = 0
        for pattern in matched_patterns:
            linkedin_backing_count += int(pattern.get("linkedin_backing_count", 0) or 0)
            alumni_source_strength += int(pattern.get("source_strength", 0) or 0)
            for provider, count in dict(pattern.get("provider_counts", {})).items():
                matched_provider_counts[provider] = matched_provider_counts.get(provider, 0) + int(count or 0)

        score_components = dict(opportunity.get("score_components", {}))
        score_components["alumni_signal_strength"] = min(
            18,
            alumni_evidence_count * 2 + linkedin_backing_count + min(4, alumni_source_strength // 3),
        )
        score_components["trajectory_similarity"] = min(
            12,
            (6 if opportunity.get("track") in matched_path_tags and linkedin_backing_count else 0)
            + (4 if opportunity.get("track") in matched_path_tags and not linkedin_backing_count else 0)
            + min(8, len(matched_patterns) * 2),
        )
        score_components["resource_leverage_fit"] = min(
            10,
            sum(
                3
                for pattern in matched_patterns
                if pattern.get("entity_type") in {"professor", "lab", "center", "program", "resource"}
            ),
        )
        score_components["vault_alignment"] = _vault_alignment_score(opportunity)

        fit_reasons = list(opportunity.get("fit_reasons", []))
        if matched_patterns:
            if linkedin_backing_count:
                fit_reasons.append(
                    f"LinkedIn-backed across {linkedin_backing_count} UIUC student/alumni profiles via {', '.join(pattern['entity_name'] for pattern in matched_patterns[:3])}."
                )
            else:
                fit_reasons.append(
                    f"Supported by fallback public UIUC evidence via {', '.join(pattern['entity_name'] for pattern in matched_patterns[:3])}."
                )
            if any(pattern.get("entity_type") in {"center", "program", "resource"} for pattern in matched_patterns):
                fit_reasons.append("Illinois resource usage suggests this is a realistic stepping stone, not just a prestige match.")

        evidence_sources = list(dict.fromkeys([*(opportunity.get("evidence_sources") or ["official"]), *(["alumni"] if matched_patterns else [])]))
        alumni_patterns = [pattern["entity_name"] for pattern in matched_patterns]

        updated = {
            **opportunity,
            "score_components": score_components,
            "total_score": sum(score_components.values()),
            "fit_reasons": list(dict.fromkeys(fit_reasons)),
            "evidence_sources": evidence_sources,
            "alumni_patterns": alumni_patterns,
            "alumni_evidence_count": alumni_evidence_count,
            "alumni_evidence_providers": sorted(matched_provider_counts),
            "alumni_source_strength": alumni_source_strength,
            "linkedin_backing_count": linkedin_backing_count,
        }
        updated["should_ping"] = (
            updated["total_score"] >= 95
            and updated.get("next_action") in {"apply_now", "reach_out"}
        )
        enriched.append(updated)

    return sorted(enriched, key=lambda item: item.get("total_score", 0), reverse=True)
