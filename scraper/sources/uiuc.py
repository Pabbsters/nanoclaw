"""UIUC scout sources: curated seed targets plus a few official opportunity pages."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from html import unescape
from urllib.parse import urljoin, urlsplit
from xml.etree import ElementTree

import httpx

from uiuc_config import UIUC_SEED_TARGETS, UIUC_SOURCE_PAGES


LINK_RE = re.compile(r'<a[^>]+href="(?P<href>[^"]+)"[^>]*>(?P<label>.*?)</a>', re.IGNORECASE | re.DOTALL)
TAG_RE = re.compile(r"<[^>]+>")
INCLUDE_TITLE_RE = re.compile(
    r"\b(research experiences for undergraduates|reu|opportunit|intern|internship|fellowship|program|faculty and student opportunities|undergraduate research|research conference)\b",
    re.IGNORECASE,
)

EXCLUDE_TITLE_RE = re.compile(
    r"\b(student affairs|interview room|career journey|pre-health|vice chancellor|consulting|data analytics|research software|research consulting|office of|certificate|conference|learn more)\b",
    re.IGNORECASE,
)

JSON_LD_RE = re.compile(r'<script[^>]+application/ld\+json[^>]*>(?P<json>.*?)</script>', re.IGNORECASE | re.DOTALL)
META_DESCRIPTION_RE = re.compile(r'<meta[^>]+name="description"[^>]+content="(?P<desc>[^"]+)"', re.IGNORECASE)
TITLE_RE = re.compile(r"<title>\s*(?P<title>.*?)\s*</title>", re.IGNORECASE | re.DOTALL)
PROFILE_LINK_RE = re.compile(
    r"(?:/about/directory/faculty/[a-z0-9\-]+|/about/people/faculty/[a-z0-9\-]+|/about/directory/faculty/profile/[a-z0-9\-]+|/directory/profile/[a-z0-9\-]+|/people/[a-z0-9\-]+)",
    re.IGNORECASE,
)
SELF_PAGE_TARGET_RE = re.compile(
    r"\b(machine learning|artificial intelligence|computer vision|nlp|knowledge graph|deep learning|research|research engineer|data science|analytics|computational|optimization|time series|quant|fintech|autonomy|robotics|medicine|health|scientific computing)\b",
    re.IGNORECASE,
)
LAST_SOURCE_HEALTH: list[dict] = []


def _strip_html(value: str) -> str:
    return unescape(TAG_RE.sub(" ", value or "")).strip()


def _keyword_pattern(keyword: str) -> re.Pattern[str]:
    escaped = re.escape(keyword.strip().lower())
    escaped = escaped.replace(r"\ ", r"[\s\-]+")
    return re.compile(rf"(?<![a-z0-9]){escaped}(?![a-z0-9])", re.IGNORECASE)


def _contains_keyword(text: str, keyword: str) -> bool:
    return bool(_keyword_pattern(keyword).search(text))


def parse_research_park(html: str, page: dict[str, str]) -> list[dict]:
    """Extract Research Park job links from the job board page."""
    results: list[dict] = []
    for match in LINK_RE.finditer(html):
        href = match.group("href")
        if "/job/" not in href:
            continue
        title = _strip_html(match.group("label"))
        if not title:
            continue
        results.append(
            {
                "source": page["source"],
                "url": urljoin(page["url"], href),
                "entity_kind": page["entity_kind"],
                "title": title,
                "unit": page["unit"],
                "department": page["department"],
                "faculty": "",
                "description": title,
                "contact": "",
                "last_seen": "",
                "status_hint": "open",
                "domain_tags": [],
            }
        )
    return results


def parse_research_park_sitemap(xml: str) -> list[str]:
    """Extract Research Park company/detail URLs from the sitemap XML."""
    try:
        root = ElementTree.fromstring(xml)
    except ElementTree.ParseError:
        return []

    urls: list[str] = []
    namespace = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    for node in root.findall(".//sm:loc", namespace):
        url = (node.text or "").strip()
        if not url:
            continue
        slug = url.rstrip("/").rsplit("/", 1)[-1]
        if any(token in slug for token in ("summit", "event", "conference", "award", "news", "software-resources")):
            continue
        urls.append(url)
    return urls


def parse_research_park_company_page(html: str, url: str) -> dict | None:
    """Parse a Research Park company page into a scout record."""
    title = ""
    domain_tags: list[str] = []

    for match in JSON_LD_RE.finditer(html):
        try:
            payload = json.loads(match.group("json"))
        except json.JSONDecodeError:
            continue

        graph = payload.get("@graph") if isinstance(payload, dict) else None
        items = graph if isinstance(graph, list) else [payload]
        for item in items:
            if not isinstance(item, dict):
                continue
            if not title:
                title = _strip_html(str(item.get("headline") or item.get("name") or ""))
                if title.endswith("| Research Park"):
                    title = title.replace("| Research Park", "").strip()
            section = _strip_html(str(item.get("articleSection", "")))
            if section:
                for part in [piece.strip() for piece in section.split(",") if piece.strip()]:
                    domain_tags.append(part)
                    if "ai and analytics" in part.lower():
                        domain_tags.extend(["AI", "Analytics"])

    if not title:
        title_match = TITLE_RE.search(html)
        if title_match:
            title = _strip_html(title_match.group("title").replace("| Research Park", ""))

    desc_match = META_DESCRIPTION_RE.search(html)
    description = _strip_html(desc_match.group("desc")) if desc_match else ""

    combined = f"{title} {description} {' '.join(domain_tags)}".lower()
    if any(_contains_keyword(combined, keyword) for keyword in ("campus resources", "wins", "world cup", "recognition", "news", "award")):
        return None

    technical_signals = (
        "software",
        "ai",
        "analytics",
        "engineering",
        "computer science",
        "data",
        "statistics",
        "operations research",
        "robotics",
        "machine learning",
        "research and development",
        "intern program",
        "financial services",
        "fintech",
        "credit cards",
        "simulation",
        "deep-tech",
    )
    if not any(_contains_keyword(combined, keyword) for keyword in technical_signals):
        return None

    normalized_tags = sorted({tag.lower() for tag in domain_tags if tag.strip()})
    return {
        "source": "research_park_sitemap",
        "url": url,
        "entity_kind": "research_group",
        "title": title,
        "unit": "Research Park",
        "department": "Research Park",
        "faculty": "",
        "description": description,
        "contact": "",
        "last_seen": "",
        "status_hint": "rolling",
        "domain_tags": normalized_tags,
    }


def parse_generic(html: str, page: dict[str, str]) -> list[dict]:
    """Extract opportunity-like links from general Illinois pages."""
    results: list[dict] = []
    for match in LINK_RE.finditer(html):
        label = _strip_html(match.group("label"))
        if not label or not INCLUDE_TITLE_RE.search(label):
            continue
        if EXCLUDE_TITLE_RE.search(label):
            continue
        href = urljoin(page["url"], match.group("href"))
        results.append(
            {
                "source": page["source"],
                "url": href,
                "entity_kind": page["entity_kind"],
                "title": label,
                "unit": page["unit"],
                "department": page["department"],
                "faculty": "",
                "description": label,
                "contact": "",
                "last_seen": "",
                "status_hint": "rolling",
                "domain_tags": [],
            }
        )
    return results


def parse_faculty_link_hub(html: str, page: dict[str, str]) -> list[str]:
    """Extract faculty profile links from official Illinois research/faculty hub pages."""
    seen: set[str] = set()
    urls: list[str] = []
    index_slugs = {
        "faculty",
        "staff",
        "administration",
        "yearbook",
        "adjuncts-affiliates",
        "emeriti-faculty",
        "deans-cabinet",
        "directory",
        "committees",
        "doctoral-students",
    }

    for match in LINK_RE.finditer(html):
        href = match.group("href")
        full_url = urljoin(page["url"], href)
        label = _strip_html(match.group("label"))
        lowered_label = label.lower()
        slug = urlsplit(full_url).path.rstrip("/").rsplit("/", 1)[-1].lower()
        profile_link_pattern = str(page.get("profile_link_pattern", "") or "")

        if not PROFILE_LINK_RE.search(full_url):
            continue
        if profile_link_pattern and profile_link_pattern not in full_url:
            continue
        if any(token in full_url for token in ("/courses/profile/", "/jobs/", "/directory/faculty-dept", "/emeritus", "/chairs")):
            continue
        if slug in index_slugs:
            continue
        if any(
            token in lowered_label
            for token in (
                "administration",
                "yearbook",
                "staff",
                "committees",
                "adjuncts",
                "emeriti",
                "doctoral students",
                "deans cabinet",
            )
        ):
            continue
        if any(token in lowered_label for token in ("faculty (tenure track)", "teaching faculty", "find people", "faculty")) and len(label.split()) <= 3:
            continue
        if full_url in seen:
            continue
        seen.add(full_url)
        urls.append(full_url)

    return urls


def parse_self_page(html: str, page: dict[str, str]) -> list[dict]:
    """Parse a single Illinois program/lab page into one scout-ready record."""
    title_match = TITLE_RE.search(html)
    title = _strip_html(title_match.group("title")) if title_match else str(page.get("source", "Illinois page"))
    title = (
        title.replace("| Illinois", "")
        .replace("| UIUC", "")
        .replace("| Gies College of Business", "")
        .replace("| Carle Illinois College of Medicine", "")
        .replace("| Center for Digital Agriculture", "")
        .strip()
    )
    desc_match = META_DESCRIPTION_RE.search(html)
    description = _strip_html(desc_match.group("desc")) if desc_match else ""
    page_text = _strip_html(html)
    combined = f"{title} {description} {page_text}".lower()
    if not SELF_PAGE_TARGET_RE.search(combined):
        return []

    domain_tags = sorted(
        {
            keyword
            for keyword in (
                "machine learning",
                "artificial intelligence",
                "data science",
                "analytics",
                "computational",
                "research",
                "quant",
                "fintech",
                "optimization",
                "time series",
                "autonomy",
                "robotics",
                "medicine",
                "health",
            )
            if _contains_keyword(combined, keyword)
        }
    )
    return [
        {
            "source": page["source"],
            "url": page["url"],
            "entity_kind": page["entity_kind"],
            "title": title,
            "unit": page["unit"],
            "department": page["department"],
            "faculty": "",
            "description": description or " ".join(page_text.split()[:80]).strip(),
            "contact": "",
            "last_seen": "",
            "status_hint": "rolling" if any(_contains_keyword(combined, keyword) for keyword in ("reu", "apply", "student", "intern", "request", "consultation")) else "unknown",
            "domain_tags": domain_tags,
        }
    ]


def parse_faculty_profile_page(html: str, url: str, page: dict[str, str]) -> dict | None:
    """Parse a faculty profile page and keep it only when the research matches target themes."""
    title_match = TITLE_RE.search(html)
    raw_title = _strip_html(title_match.group("title")) if title_match else ""
    title = (
        raw_title.replace("| Electrical & Computer Engineering | Illinois", "")
        .replace("| The Grainger College of Engineering | Illinois", "")
        .replace("| Carle Illinois College of Medicine | Illinois", "")
        .replace("| Bioengineering | Illinois", "")
        .replace("| Statistics at Illinois", "")
        .replace("| Department of Statistics | Illinois", "")
        .replace("| Neuroscience Program | Illinois", "")
        .replace("| School of Information Sciences | Illinois", "")
        .replace("| Industrial & Enterprise Systems Engineering", "")
        .replace("| Illinois", "")
        .strip()
    )
    if (
        not re.search(r"[a-z]", title, re.IGNORECASE)
        or title.startswith("|")
        or title.lower() in {
            "siebel school of computing and data science",
            "school of information sciences",
            "bioengineering",
            "statistics at illinois",
        }
    ):
        return None

    desc_match = META_DESCRIPTION_RE.search(html)
    description = _strip_html(desc_match.group("desc")) if desc_match else ""
    page_text = _strip_html(html)
    combined = f"{title} {description} {page_text}".lower()

    target_signals = (
        "machine learning",
        "artificial intelligence",
        "computer vision",
        "natural language",
        "nlp",
        "knowledge graph",
        "deep learning",
        "robotics",
        "autonomy",
        "perception",
        "generative",
        "trustworthy ai",
        "robustness",
        "verification",
        "scientific computing",
        "data science",
        "quantitative",
        "optimization",
        "time series",
        "medical ai",
        "computational imaging",
        "biomedical",
    )
    if not any(_contains_keyword(combined, keyword) for keyword in target_signals):
        return None

    domain_tags = sorted(
        {
            keyword
            for keyword in target_signals
            if _contains_keyword(combined, keyword)
        }
    )
    summary = description
    if not summary:
        summary = " ".join(page_text.split()[:80]).strip()

    return {
        "source": page["source"],
        "url": url,
        "entity_kind": "faculty_profile",
        "title": title,
        "unit": page["unit"],
        "department": page["department"],
        "faculty": title,
        "description": summary,
        "contact": "",
        "last_seen": "",
        "status_hint": "rolling",
        "domain_tags": domain_tags,
    }


PARSERS = {
    "research_park": parse_research_park,
    "generic": parse_generic,
    "self_page": parse_self_page,
}


async def _fetch_page(page: dict[str, str]) -> list[dict]:
    if page["parser"] == "research_park_sitemap":
        return await _fetch_research_park_sitemap(page)
    if page["parser"] == "faculty_link_hub":
        return await _fetch_faculty_link_hub(page)

    parser = PARSERS[page["parser"]]
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        text = await _get_page_text_for_page(client, page)
        return parser(text, page)


async def _fetch_research_park_sitemap(page: dict[str, str]) -> list[dict]:
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        sitemap_text = await _get_page_text_for_page(client, page)
        company_urls = parse_research_park_sitemap(sitemap_text)

        results: list[dict] = []
        for url in company_urls[:15]:
            try:
                company_text = await _get_page_text_for_page(client, {**page, "url": url})
                record = parse_research_park_company_page(company_text, url)
                if record is not None:
                    results.append(record)
            except Exception:
                continue
        return results


async def _fetch_faculty_link_hub(page: dict[str, str]) -> list[dict]:
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        hub_text = await _get_page_text_for_page(client, page)
        faculty_urls = parse_faculty_link_hub(hub_text, page)
        max_profiles = int(page.get("max_profiles", 25) or 25)

        results: list[dict] = []
        for url in faculty_urls[:max_profiles]:
            try:
                faculty_text = await _get_page_text_for_page(client, {**page, "url": url})
                record = parse_faculty_profile_page(faculty_text, url, page)
                if record is not None:
                    results.append(record)
            except Exception:
                continue
        return results


async def _get_page_text(client: httpx.AsyncClient, url: str) -> str:
    return await _get_page_text_for_page(client, {"url": url})


async def _get_page_text_for_page(client: httpx.AsyncClient, page: dict[str, object]) -> str:
    url = str(page["url"])
    if page.get("use_curl_only"):
        fallback = _curl_fetch(url)
        if fallback:
            return fallback
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
    text = response.text
    if response.status_code >= 400 or _is_cloudflare_block(text):
        fallback = _curl_fetch(url)
        if fallback:
            return fallback
    response.raise_for_status()
    return text


def _is_cloudflare_block(text: str) -> bool:
    lowered = text.lower()
    return "just a moment" in lowered or "attention required" in lowered or "sorry, you have been blocked" in lowered


def _curl_fetch(url: str) -> str | None:
    curl_path = shutil.which("curl")
    if not curl_path:
        return None

    try:
        result = subprocess.run(
            [
                curl_path,
                "-sS",
                "-A",
                (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/135.0.0.0 Safari/537.36"
                ),
                "-H",
                "Accept-Language: en-US,en;q=0.9",
                url,
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except Exception:
        return None

    return result.stdout or None


async def poll_all() -> list[dict]:
    """Fetch UIUC scout inputs from official pages and curated seeds."""
    global LAST_SOURCE_HEALTH
    results = [dict(record) for record in UIUC_SEED_TARGETS]
    health_records: list[dict] = []
    for page in UIUC_SOURCE_PAGES:
        try:
            page_results = await _fetch_page(page)
            results.extend(page_results)
            health_records.append(
                {
                    "source": page["source"],
                    "url": page["url"],
                    "status": "healthy",
                    "records_found": len(page_results),
                }
            )
        except Exception as exc:
            status = "blocked" if "403" in str(exc) else "rate_limited" if "429" in str(exc) else "error"
            health_records.append(
                {
                    "source": page["source"],
                    "url": page["url"],
                    "status": status,
                    "records_found": 0,
                    "error": str(exc),
                }
            )
            continue
    LAST_SOURCE_HEALTH = health_records
    return results


def get_last_source_health() -> list[dict]:
    return [dict(item) for item in LAST_SOURCE_HEALTH]
