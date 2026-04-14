"""Track classification engine for job postings."""

from __future__ import annotations

import re
from typing import Optional

from config import EXCLUDE_PATTERNS, INTERN_TITLE_PATTERNS, TRACK_KEYWORDS, TRACK_PRIORITY


def _is_bachelor_level(title: str, description: str) -> bool:
    """Return True if the posting is appropriate for a bachelor's student.

    Requires at least one intern/entry-level signal in the title AND
    no disqualifying patterns (PhD required, senior, 5+ years, etc.).
    """
    title_lower = title.lower()
    combined_lower = f"{title} {description}".lower()

    # Must have an intern/entry-level signal in the title
    if not any(re.search(p, title_lower) for p in INTERN_TITLE_PATTERNS):
        return False

    # Must not contain any disqualifying patterns anywhere
    if any(re.search(p, combined_lower) for p in EXCLUDE_PATTERNS):
        return False

    return True


def classify_posting(title: str, description: str = "") -> Optional[dict]:
    """Classify a posting into the highest-priority matching track.

    Only returns a match for postings appropriate for a bachelor's student
    (intern, new grad, entry-level, no PhD/senior requirements).

    Returns:
        A dict with keys ``track``, ``priority``, and ``matched_keyword``
        for the highest-priority match, or ``None`` if nothing matches.
    """
    if not title and not description:
        return None

    if not _is_bachelor_level(title, description):
        return None

    combined = f"{title} {description}".lower()

    for priority, track in enumerate(TRACK_PRIORITY):
        keywords = TRACK_KEYWORDS.get(track, [])
        for keyword in keywords:
            pattern = rf"\b{re.escape(keyword)}\b"
            if re.search(pattern, combined):
                return {
                    "track": track,
                    "priority": priority,
                    "matched_keyword": keyword,
                }

    return None
