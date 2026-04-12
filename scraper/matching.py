"""Track classification engine for job postings."""

from __future__ import annotations

import re
from typing import Optional

from config import TRACK_KEYWORDS, TRACK_PRIORITY


def classify_posting(title: str, description: str = "") -> Optional[dict]:
    """Classify a posting into the highest-priority matching track.

    Combines title and description, lowercases the text, then checks each
    track's keywords using word-boundary regex in priority order.

    Returns:
        A dict with keys ``track``, ``priority``, and ``matched_keyword``
        for the highest-priority match, or ``None`` if nothing matches.
    """
    if not title and not description:
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
