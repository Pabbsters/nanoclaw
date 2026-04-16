"""Helpers for loading project environment variables for the scraper."""

from __future__ import annotations

import os
from pathlib import Path


def load_project_env() -> None:
    """Load the repo-root .env into process env without overriding existing vars."""
    candidates = [
        Path(__file__).resolve().parent.parent / ".env",
        Path.cwd().parent / ".env",
    ]

    for path in candidates:
        if not path.exists():
            continue
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())
        return
