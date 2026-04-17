"""Outreach-draft generation and quality gating for UIUC cold outreach."""

from __future__ import annotations

import asyncio
import os
import re
from dataclasses import dataclass
from html import unescape
from pathlib import Path
from typing import Any

import httpx


TAG_RE = re.compile(r"<[^>]+>")
SCRIPT_STYLE_RE = re.compile(r"<(script|style)\b[^>]*>.*?</\1>", re.IGNORECASE | re.DOTALL)
PARAGRAPH_RE = re.compile(r"<p\b[^>]*>(?P<body>.*?)</p>", re.IGNORECASE | re.DOTALL)
META_DESCRIPTION_RE = re.compile(r'<meta[^>]+name="description"[^>]+content="(?P<desc>[^"]+)"', re.IGNORECASE)
TITLE_RE = re.compile(r"<title>\s*(?P<title>.*?)\s*</title>", re.IGNORECASE | re.DOTALL)
EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w.-]+\.\w+\b")
PHONE_RE = re.compile(r"\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}")
BACKGROUND_RE = re.compile(r"^\*\*Background\*\*:\s*(?P<value>.+)$", re.MULTILINE)
LAST_UPDATED_RE = re.compile(r"^\*\*Last updated\*\*:\s*(?P<value>.+)$", re.MULTILINE)
ROLE_MARKER_RE = re.compile(r"\*\*(?P<value>.+?)\*\*")
SKILL_BULLET_RE = re.compile(r"^- \*\*(?P<value>.+?)\*\*", re.MULTILINE)

CAREER_TRACKS_PATH = Path.home() / "Vault" / "NanoClaw" / "career-plan" / "career-tracks.md"
BASE_PROVEN_SKILLS: tuple[str, ...] = (
    "Python",
    "machine learning",
    "computer vision",
    "RAG",
    "evaluation",
    "statistics",
    "quantitative modeling",
    "research tooling",
    "backtesting",
    "data systems",
)
GENERIC_HOOK_PATTERNS: tuple[str, ...] = (
    "no description captured",
    "student pathway",
    "repeated illinois",
    "official illinois",
    "research opportunity",
)
GENERIC_TAGS: tuple[str, ...] = (
    "artificial intelligence",
    "ai",
    "data",
    "research",
)
TARGET_KEYWORDS: tuple[str, ...] = (
    "trustworthy ai",
    "robustness",
    "privacy",
    "security",
    "knowledge graph",
    "nlp",
    "natural language processing",
    "computer vision",
    "multimodal",
    "generative",
    "machine learning",
    "deep learning",
    "robotics",
    "autonomy",
    "time series",
    "optimization",
    "forecasting",
    "quant",
    "trading",
    "fintech",
    "biomedical",
    "medicine",
    "signals",
    "research software",
    "data systems",
    "compiler",
    "retrieval",
    "evaluation",
)
RESEARCH_VERBS: tuple[str, ...] = (
    "studies",
    "focuses on",
    "works on",
    "investigates",
    "develops",
    "builds",
    "applies",
    "models",
    "explores",
    "research interests",
    "interests include",
    "group studies",
    "lab studies",
)
NOISY_HOOK_PATTERNS: tuple[str, ...] = (
    "we use cookies",
    "use of cookies",
    "cookie preferences",
    "accept cookies",
    "alumni & donor",
    "coordinator",
    "contact us",
    "office hours",
    "phone:",
    "fax:",
    "room ",
    "building",
    "schedule an appointment",
    "monday - friday",
    "saturday:",
    "sunday:",
    "a.m.",
    "p.m.",
    "closed.",
    "copyright",
    "all content on this site",
    "rights are reserved",
    "data mining",
    "lecture series",
    "receives gift",
    "powered by pure",
    "link opens in a new tab",
    "scopus",
    "fingerprint engine",
)
OFFICIAL_RESEARCH_HOST_MARKERS: tuple[str, ...] = (
    "illinois.edu",
    "uiuc.edu",
)
TAG_FALLBACK_REVIEW_REASON = (
    "Hook is based on broad topic tags rather than a specific official research summary."
)
DEFAULT_EMAIL_INTRO = (
    "My name is Ruthwik Pabbu, and I am a student at the University of Illinois Urbana-Champaign studying "
    "Statistics and Computer Science. I am reaching out to ask whether you might be open to an undergraduate "
    "researcher or technical contributor in your group."
)


@dataclass
class OutreachProfileSnapshot:
    source_path: str
    background_summary: str
    last_updated: str
    tier1_roles: tuple[str, ...]
    tier2_roles: tuple[str, ...]
    adjacent_skill_groups: dict[str, tuple[str, ...]]
    adjacent_skills_in_progress: tuple[str, ...]
    excluded_skills: tuple[str, ...]
    proven_skills: tuple[str, ...]


def _clean_text(value: str | None) -> str:
    return re.sub(r"\s+", " ", (value or "")).strip()


def _strip_html(value: str) -> str:
    return _clean_text(unescape(TAG_RE.sub(" ", value or "")))


def _clean_page_text(value: str) -> str:
    return _strip_html(SCRIPT_STYLE_RE.sub(" ", value or ""))


def _extract_paragraphs(html: str, limit: int = 6) -> list[str]:
    paragraphs: list[str] = []
    for match in PARAGRAPH_RE.finditer(html or ""):
        snippet = _strip_html(match.group("body"))
        if len(snippet.split()) < 6:
            continue
        paragraphs.append(snippet)
        if len(paragraphs) >= limit:
            break
    return paragraphs


def _split_sentences(text: str) -> list[str]:
    if not text:
        return []
    return [
        sentence.strip()
        for sentence in re.split(r"(?<=[.!?])\s+", text)
        if len(sentence.strip().split()) >= 5
    ]


async def _fetch_page_context(url: str) -> dict[str, Any]:
    if not url:
        return {}
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            response = await client.get(
                url,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/135.0.0.0 Safari/537.36"
                    ),
                    "Accept-Language": "en-US,en;q=0.9",
                },
            )
            response.raise_for_status()
    except Exception:
        return {}

    html = response.text
    desc_match = META_DESCRIPTION_RE.search(html)
    title_match = TITLE_RE.search(html)
    page_text = _clean_page_text(html)
    paragraphs = _extract_paragraphs(html)
    return {
        "url": url,
        "title": _strip_html(title_match.group("title")) if title_match else "",
        "description": _strip_html(desc_match.group("desc")) if desc_match else "",
        "paragraphs": paragraphs,
        "page_text": page_text,
        "sentences": _split_sentences(" ".join(paragraphs) or page_text),
    }


def _extract_section(markdown: str, heading_prefix: str, level: int = 2) -> str:
    target_prefix = "#" * level + " "
    stop_prefixes = tuple("#" * depth + " " for depth in range(1, level + 1))
    lines = markdown.splitlines()
    collecting = False
    collected: list[str] = []

    for line in lines:
        if line.startswith(target_prefix) and line[len(target_prefix):].startswith(heading_prefix):
            collecting = True
            continue
        if collecting and line.startswith(stop_prefixes):
            break
        if collecting:
            collected.append(line)

    return "\n".join(collected).strip()


def _parse_role_table(section_text: str) -> tuple[str, ...]:
    roles: list[str] = []
    for line in section_text.splitlines():
        if not line.startswith("|"):
            continue
        matches = ROLE_MARKER_RE.findall(line)
        if not matches:
            continue
        roles.append(_clean_text(matches[0]))
    return tuple(roles)


def _parse_skill_bullets(section_text: str) -> tuple[str, ...]:
    return tuple(_clean_text(match) for match in SKILL_BULLET_RE.findall(section_text))


def _parse_excluded_skills(section_text: str) -> tuple[str, ...]:
    skills: list[str] = []
    for line in section_text.splitlines():
        if not line.startswith("- ❌"):
            continue
        raw_value = line.removeprefix("- ❌").strip()
        if "—" in raw_value:
            raw_value = raw_value.split("—", 1)[0].strip()
        skills.append(_clean_text(raw_value))
    return tuple(skills)


def _normalize_role_name(role: str) -> str:
    cleaned = role.replace("—", ",")
    cleaned = re.sub(r"\(.*?\)", "", cleaned)
    cleaned = cleaned.replace("/", " / ")
    cleaned = _clean_text(cleaned).replace(" ,", ",")
    return cleaned


def _format_list_phrase(items: list[str]) -> str:
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return f"{', '.join(items[:-1])}, and {items[-1]}"


def _resolve_career_tracks_path(profile_path: str | Path | None = None) -> Path:
    if profile_path is not None:
        return Path(profile_path).expanduser()
    env_profile_path = _clean_text(os.environ.get("UIUC_OUTREACH_PROFILE_PATH", ""))
    if env_profile_path:
        return Path(env_profile_path).expanduser()
    return CAREER_TRACKS_PATH


def load_outreach_profile_snapshot(profile_path: str | Path | None = None) -> OutreachProfileSnapshot:
    resolved_path = _resolve_career_tracks_path(profile_path)
    try:
        markdown = resolved_path.read_text(encoding="utf-8")
    except OSError:
        return OutreachProfileSnapshot(
            source_path=str(resolved_path),
            background_summary="Statistics and Computer Science at UIUC",
            last_updated="unknown",
            tier1_roles=("ML Engineer", "AI Engineer", "Python Backend / AI Engineer"),
            tier2_roles=("Data Scientist", "Data Engineer", "Quantitative Analyst"),
            adjacent_skill_groups={
                "MLOps Stack": ("MLflow", "Weights & Biases (W&B)", "Kubeflow", "SageMaker"),
                "AI Engineering Stack": ("LangChain", "LlamaIndex", "Vector DBs"),
                "Cloud / DevOps Foundations": ("AWS Solutions Architect Associate cert", "Docker", "Kubernetes", "Terraform"),
            },
            adjacent_skills_in_progress=(
                "MLflow",
                "Weights & Biases (W&B)",
                "LangChain",
                "LlamaIndex",
                "Vector DBs",
                "Docker",
                "Kubernetes",
                "Terraform",
            ),
            excluded_skills=("Embedded systems", "Security certs", "Solidity / Swift / Kotlin", "C++"),
            proven_skills=BASE_PROVEN_SKILLS,
        )

    background_match = BACKGROUND_RE.search(markdown)
    updated_match = LAST_UPDATED_RE.search(markdown)
    tier1_section = _extract_section(markdown, "Tier 1")
    tier2_section = _extract_section(markdown, "Tier 2")
    adjacent_section = _extract_section(markdown, "Adjacent Skills to Add")
    mlops_section = _extract_section(adjacent_section, "MLOps Stack", level=3)
    ai_eng_section = _extract_section(adjacent_section, "AI Engineering Stack", level=3)
    cloud_section = _extract_section(adjacent_section, "Cloud / DevOps Foundations", level=3)
    skip_section = _extract_section(adjacent_section, "Skip These", level=3)

    adjacent_groups = {
        "MLOps Stack": _parse_skill_bullets(mlops_section),
        "AI Engineering Stack": _parse_skill_bullets(ai_eng_section),
        "Cloud / DevOps Foundations": _parse_skill_bullets(cloud_section),
    }

    adjacent_skills: list[str] = []
    for group_values in adjacent_groups.values():
        adjacent_skills.extend(group_values)

    return OutreachProfileSnapshot(
        source_path=str(resolved_path),
        background_summary=_clean_text(background_match.group("value")) if background_match else "Statistics and Computer Science at UIUC",
        last_updated=_clean_text(updated_match.group("value")) if updated_match else "unknown",
        tier1_roles=tuple(_normalize_role_name(role) for role in _parse_role_table(tier1_section)),
        tier2_roles=tuple(_normalize_role_name(role) for role in _parse_role_table(tier2_section)),
        adjacent_skill_groups=adjacent_groups,
        adjacent_skills_in_progress=tuple(dict.fromkeys(adjacent_skills)),
        excluded_skills=_parse_excluded_skills(skip_section),
        proven_skills=BASE_PROVEN_SKILLS,
    )


def _build_constant_paragraph(snapshot: OutreachProfileSnapshot) -> str:
    role_focus = _format_list_phrase(list(snapshot.tier1_roles[:3])) or "ML, AI, and research engineering"
    proven_focus = _format_list_phrase(list(snapshot.proven_skills[:5])) or "Python and machine learning"
    adjacent_focus = _format_list_phrase(list(snapshot.adjacent_skills_in_progress[:4])) or "MLflow and LangChain"
    return (
        f"Over the past year, I have been building toward {role_focus} work through projects in {proven_focus}. "
        f"I am also actively building toward {adjacent_focus} so I can grow into stronger AI engineering, MLOps, and cloud based workflows. "
        "I would be excited to contribute where my current background can help while continuing to deepen those skills in a real research setting."
    )


def get_email_constant_paragraph(profile_path: str | Path | None = None) -> str:
    return _build_constant_paragraph(load_outreach_profile_snapshot(profile_path))


def _keyword_score(text: str, tags: list[str]) -> int:
    lowered = text.lower()
    score = 0
    for keyword in [*tags, *TARGET_KEYWORDS]:
        if keyword and keyword.lower() in lowered:
            score += 2 if keyword.lower() not in GENERIC_TAGS else 1
    for verb in RESEARCH_VERBS:
        if verb in lowered:
            score += 2
    if any(token in lowered for token in ("project", "lab", "group", "method", "model", "system")):
        score += 1
    return score


def _usable_description(description: str) -> bool:
    lowered = description.lower()
    if not description or len(description.split()) < 8:
        return False
    return not any(pattern in lowered for pattern in GENERIC_HOOK_PATTERNS)


def _is_noisy_hook(text: str) -> bool:
    lowered = text.lower()
    if EMAIL_RE.search(text) or PHONE_RE.search(text):
        return True
    if re.search(r"\.[a-z0-9_-]+\s*\{", text, re.IGNORECASE):
        return True
    if any(marker in lowered for marker in ("fill:", "stroke:", "font-family:", "font-size:")):
        return True
    return any(pattern in lowered for pattern in NOISY_HOOK_PATTERNS)


def _looks_like_tag_list(text: str) -> bool:
    lowered = text.lower()
    if len(text.split()) <= 6 and "," in text:
        return True
    return not any(marker in lowered for marker in (".", "studies", "focuses", "works on", "develops", "investigates"))


def _classify_page_text_source(text: str, opportunity: dict[str, Any]) -> str:
    lowered = text.lower()
    title = _clean_text(str(opportunity.get("title", ""))).lower()
    if any(marker in lowered for marker in ("research interests", "interests include", "my research", "his research", "her research", "works on", "focuses on", "studies")):
        return "official_bio"
    if any(marker in lowered for marker in ("lab", "group", "center", "project")):
        return "lab_summary"
    if any(marker in lowered for marker in ("program", "student", "undergraduate", "institute")):
        return "program_summary"
    if title and title in lowered:
        return "official_bio"
    return "page_summary"


def _candidate_priority(source: str) -> int:
    priorities = {
        "official_bio": 6,
        "lab_summary": 5,
        "program_summary": 4,
        "official_summary": 4,
        "page_summary": 3,
        "meta_description": 2,
        "tag_fallback": 1,
    }
    return priorities.get(source, 0)


def _pick_hook(opportunity: dict[str, Any], page_context: dict[str, Any]) -> dict[str, str]:
    tags = [
        _clean_text(str(tag))
        for tag in (opportunity.get("tags") or [])
        if _clean_text(str(tag)).lower() not in GENERIC_TAGS
    ]
    candidates: list[dict[str, str]] = []

    description = _clean_text(str(opportunity.get("description", "")))
    if _usable_description(description):
        candidates.append({"text": description, "source": "official_summary"})

    page_description = _clean_text(str(page_context.get("description", "")))
    if _usable_description(page_description):
        candidates.append({"text": page_description, "source": "meta_description"})

    for paragraph in page_context.get("paragraphs", [])[:4]:
        cleaned = _clean_text(paragraph)
        if not cleaned or _is_noisy_hook(cleaned):
            continue
        candidates.append(
            {
                "text": cleaned,
                "source": _classify_page_text_source(cleaned, opportunity),
            }
        )

    if not candidates:
        for sentence in page_context.get("sentences", [])[:5]:
            cleaned = _clean_text(sentence)
            if not cleaned or _is_noisy_hook(cleaned):
                continue
            candidates.append(
                {
                    "text": cleaned,
                    "source": _classify_page_text_source(cleaned, opportunity),
                }
            )

    ranked = sorted(
        candidates,
        key=lambda candidate: (
            _candidate_priority(candidate["source"]),
            _keyword_score(candidate["text"], tags),
            len(candidate["text"]),
        ),
        reverse=True,
    )
    if ranked:
        return ranked[0]

    tag_text = ", ".join(tags[:2]) if tags else _clean_text(str(opportunity.get("title", "")))
    return {
        "text": tag_text,
        "source": "tag_fallback",
    }


def _tag_fallback_hook(opportunity: dict[str, Any]) -> dict[str, str]:
    tags = [
        _clean_text(str(tag))
        for tag in (opportunity.get("tags") or [])
        if _clean_text(str(tag)).lower() not in GENERIC_TAGS
    ]
    tag_text = ", ".join(tags[:2]) if tags else _clean_text(str(opportunity.get("title", "")))
    return {
        "text": tag_text,
        "source": "tag_fallback",
    }


def _topic_clause(opportunity: dict[str, Any], hook_text: str) -> str:
    tags = [
        _clean_text(str(tag))
        for tag in (opportunity.get("tags") or [])
        if _clean_text(str(tag)).lower() not in GENERIC_TAGS
    ]
    if tags:
        if len(tags) == 1:
            return tags[0]
        return f"{tags[0]} and {tags[1]}"

    title = _clean_text(str(opportunity.get("title", "")))
    if title:
        return title
    return _clean_text(hook_text)


def _official_source_is_trusted(url: str, source: str) -> bool:
    if source == "tag_fallback":
        return False
    lowered_url = url.lower()
    return any(marker in lowered_url for marker in OFFICIAL_RESEARCH_HOST_MARKERS)


def _assess_hook_quality(opportunity: dict[str, Any], hook: dict[str, str]) -> tuple[str, str | None]:
    hook_text = _clean_text(hook.get("text", ""))
    source = hook.get("source", "tag_fallback")
    lowered = hook_text.lower()
    keyword_hits = sum(1 for keyword in TARGET_KEYWORDS if keyword in lowered)

    if source == "tag_fallback":
        return ("needs_review", TAG_FALLBACK_REVIEW_REASON)
    if not _official_source_is_trusted(str(opportunity.get("url", "")), source):
        return ("needs_review", "Hook did not come from a clearly official Illinois page.")
    if len(hook_text.split()) < 9:
        return ("needs_review", "Hook is too short to confirm a specific research direction.")
    if _looks_like_tag_list(hook_text):
        return ("needs_review", "Hook is still broad and reads like a topic list instead of a research summary.")
    if keyword_hits == 0 and not any(verb in lowered for verb in RESEARCH_VERBS):
        return ("needs_review", "Hook does not contain a clear research theme, method, or project signal.")
    return ("send_ready", None)


def _trim_evidence(text: str, limit: int = 220) -> str:
    cleaned = _clean_text(text)
    if len(cleaned) <= limit:
        return cleaned.rstrip(" .,;:")
    return cleaned[:limit].rstrip(" .,;:") + "..."


def _topic_keywords(opportunity: dict[str, Any]) -> str:
    tags = [
        _clean_text(str(tag))
        for tag in (opportunity.get("tags") or [])
        if _clean_text(str(tag)).lower() not in GENERIC_TAGS
    ]
    return " ".join(tags).lower()


def _build_skill_alignment(opportunity: dict[str, Any], snapshot: OutreachProfileSnapshot) -> list[str]:
    searchable_text = " ".join(
        [
            _topic_keywords(opportunity),
            _clean_text(str(opportunity.get("description", ""))).lower(),
            _clean_text(str(opportunity.get("title", ""))).lower(),
            _clean_text(str(opportunity.get("track", ""))).lower(),
        ]
    )

    alignment: list[str] = []

    proven_skill_signals = {
        "Python": ("python", "backend", "tooling"),
        "machine learning": ("machine learning", "deep learning", "model", "inference"),
        "computer vision": ("computer vision", "vision", "perception", "multimodal"),
        "RAG": ("retrieval", "rag", "knowledge graph", "llm", "nlp"),
        "evaluation": ("evaluation", "benchmark", "robustness"),
        "statistics": ("statistics", "causal", "quantitative", "forecasting"),
        "quantitative modeling": ("quant", "optimization", "time series", "forecasting", "trading"),
        "research tooling": ("tooling", "research software", "experimentation", "reproducible"),
        "backtesting": ("trading", "portfolio", "backtest", "asset pricing"),
        "data systems": ("data systems", "platform", "pipeline", "infra", "compiler"),
    }
    for skill_name, signals in proven_skill_signals.items():
        if any(signal in searchable_text for signal in signals):
            alignment.append(skill_name)

    if opportunity.get("track") == "quant_fintech":
        for fallback_skill in ("statistics", "quantitative modeling", "backtesting"):
            if fallback_skill not in alignment:
                alignment.append(fallback_skill)
    elif opportunity.get("track") == "ml_ai_research":
        for fallback_skill in ("Python", "machine learning"):
            if fallback_skill not in alignment:
                alignment.append(fallback_skill)

    adjacent_groups = snapshot.adjacent_skill_groups
    if any(signal in searchable_text for signal in ("llm", "retrieval", "rag", "knowledge graph", "vector", "generative", "nlp")):
        for skill in adjacent_groups.get("AI Engineering Stack", ())[:2]:
            alignment.append(f"building toward {skill}")
    if any(signal in searchable_text for signal in ("infra", "pipeline", "experiment", "registry", "observability", "deployment", "platform")):
        for skill in adjacent_groups.get("MLOps Stack", ())[:2]:
            alignment.append(f"building toward {skill}")
    if any(signal in searchable_text for signal in ("cloud", "systems", "deployment", "platform", "devops", "docker", "kubernetes", "terraform")):
        for skill in adjacent_groups.get("Cloud / DevOps Foundations", ())[:2]:
            alignment.append(f"building toward {skill}")

    cleaned_alignment: list[str] = []
    excluded_lower = {skill.lower() for skill in snapshot.excluded_skills}
    for item in alignment:
        stripped = _clean_text(item)
        if not stripped:
            continue
        lowered = stripped.lower().replace("building toward ", "")
        if any(excluded in lowered for excluded in excluded_lower):
            continue
        if stripped not in cleaned_alignment:
            cleaned_alignment.append(stripped)
    return cleaned_alignment[:6]


def _build_observation_paragraph(topic_clause: str, hook: dict[str, str], quality: str) -> str:
    hook_text = _trim_evidence(hook.get("text", ""))
    if quality == "needs_review" and hook.get("source") == "tag_fallback":
        paragraph = (
            f"I became interested in your research after reading about your work in {topic_clause}. "
            f"The overlap between {hook_text} and the kind of technical work I want to keep building toward is what made me want to reach out."
        )
    else:
        paragraph = (
            f"I became interested in your research after reading about your work in {topic_clause}. "
            f"I was especially interested in {hook_text}. "
            "That mix of technical depth and real research impact feels closely aligned with the kind of work I want to grow into through hands on experience."
        )
    return re.sub(r"\s+", " ", paragraph).strip()


def _extract_name(opportunity: dict[str, Any]) -> str:
    return (
        _clean_text(str(opportunity.get("faculty_name", "")))
        or _clean_text(str(opportunity.get("title", "")))
        or "your group"
    )


def build_outreach_email_fields(
    opportunity: dict[str, Any],
    page_context: dict[str, Any] | None = None,
    profile_snapshot: OutreachProfileSnapshot | None = None,
) -> dict[str, Any]:
    """Create intro, quality, and evidence-backed custom paragraph for one cold-outreach target."""
    resolved_context = page_context or {}
    snapshot = profile_snapshot or load_outreach_profile_snapshot()
    hook = _pick_hook(opportunity, resolved_context)
    topic_clause = _topic_clause(opportunity, hook["text"])
    name = _extract_name(opportunity)
    quality, review_reason = _assess_hook_quality(opportunity, hook)
    if quality == "needs_review" and hook.get("source") != "tag_fallback":
        hook = _tag_fallback_hook(opportunity)
        topic_clause = _topic_clause(opportunity, hook["text"])
    observation_paragraph = _build_observation_paragraph(topic_clause, hook, quality)

    return {
        "email_intro": DEFAULT_EMAIL_INTRO,
        "email_observation_paragraph": observation_paragraph,
        "email_constant_template_ref": "email-template-constant.md",
        "email_target_name": name,
        "email_quality": quality,
        "email_hook_source": hook.get("source", "tag_fallback"),
        "email_supporting_evidence": _trim_evidence(hook.get("text", "")),
        "email_skill_alignment": _build_skill_alignment(opportunity, snapshot),
        "email_review_reason": review_reason,
    }


async def enrich_outreach_opportunities(
    opportunities: list[dict[str, Any]],
    *,
    fetch_live_context: bool = True,
    concurrency: int = 6,
    profile_path: str | Path | None = None,
) -> list[dict[str, Any]]:
    """Attach outreach draft fields to cold-outreach opportunities."""
    semaphore = asyncio.Semaphore(concurrency)
    snapshot = load_outreach_profile_snapshot(profile_path)

    async def enrich(opportunity: dict[str, Any]) -> dict[str, Any]:
        if opportunity.get("type") != "cold_outreach_target":
            return dict(opportunity)

        page_context: dict[str, Any] = {}
        if fetch_live_context:
            async with semaphore:
                page_context = await _fetch_page_context(str(opportunity.get("url", "")))

        return {
            **opportunity,
            **build_outreach_email_fields(opportunity, page_context, snapshot),
        }

    return [await enrich(opportunity) for opportunity in opportunities]


def build_constant_template_markdown(
    output_dir: str | Path | None = None,
    profile_path: str | Path | None = None,
) -> str:
    """Render the reusable second paragraph file for Discord pinning and outreach reuse."""
    ref = "email-template-constant.md"
    if output_dir is not None:
        ref = str(Path(output_dir).expanduser() / ref)

    snapshot = load_outreach_profile_snapshot(profile_path)
    lines = [
        "# UIUC Scout Outreach Constant Paragraph",
        "",
        "Pin this once in Discord and reuse it as the second paragraph for cold-outreach emails.",
        "",
        _build_constant_paragraph(snapshot),
        "",
        f"Profile source: `{snapshot.source_path}`",
        f"Profile last updated: `{snapshot.last_updated}`",
        f"Reference file: `{ref}`",
        "",
    ]
    return "\n".join(lines)
