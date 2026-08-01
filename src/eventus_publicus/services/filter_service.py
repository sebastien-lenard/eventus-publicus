# src/eventus-publicus/services/filter_service.py
# SPDX-FileCopyrightText: 2026 Sebastien Lenard <sebastien.lenard@gmail.com> and Contributors
# SPDX-License-Identifier: Apache-2.0
"""Service to load blacklists and filter events by title and location."""

import logging
import re
from pathlib import Path

from pydantic import BaseModel, Field

from eventus_publicus.schemas.event import Event

logger = logging.getLogger(__name__)


class BlacklistConfig(BaseModel):
    """Pydantic model representing external blacklist configuration."""

    titles: list[str] = Field(default_factory=list)
    locations: list[str] = Field(default_factory=list)


def _normalize(text: str) -> str:
    """Normalize text for bulletproof comparison.

    - Lowercases text.
    - Replaces all bullet/dash variations with standard spaces.
    - Collapses multiple whitespace characters into a single space.
    """
    if not text:
        return ""

    # Replace unicode bullets, dashes, hyphens with spaces
    normalized = re.sub(r"[·\-\—\|]", " ", text)
    # Lowercase and collapse all whitespace
    return re.sub(r"\s+", " ", normalized.lower()).strip()


def _matches_pattern(text: str, pattern: str) -> bool:
    """Check if normalized text matches a wildcard pattern containing '*'."""
    norm_text = _normalize(text)
    norm_pattern = _normalize(pattern)

    if not norm_pattern:
        return False

    # If there are no wildcards, check if the pattern is contained within text
    if "*" not in norm_pattern:
        return norm_pattern in norm_text

    # Split pattern by '*' to check sequential occurrence of sub-phrases
    chunks = [c.strip() for c in norm_pattern.split("*") if c.strip()]

    if not chunks:
        return True

    current_idx = 0
    for chunk in chunks:
        idx = norm_text.find(chunk, current_idx)
        if idx == -1:
            return False
        current_idx = idx + len(chunk)

    return True


class EventFilterService:
    """Evaluates events against configured title and location blacklists."""

    def __init__(self, config_path: Path | None = None) -> None:
        if config_path is None:
            current_dir = Path(__file__).resolve().parent
            config_path = (
                current_dir.parent.parent.parent / "config" / "blacklists.json"
            )

        self.titles: list[str] = []
        self.locations: list[str] = []

        self._load_config(config_path)

    def _load_config(self, path: Path) -> None:
        """Load and compile blacklists from JSON configuration file."""
        if not path.exists():
            logger.warning(
                "Blacklist config not found at %s. No filtering will occur.",
                path,
            )
            return

        try:
            content = path.read_text(encoding="utf-8")
            config = BlacklistConfig.model_validate_json(content)

            self.titles = config.titles
            self.locations = config.locations
            logger.info(
                "Loaded %d title rules and %d location rules from blacklist config.",
                len(self.titles),
                len(self.locations),
            )
        except Exception:
            logger.exception(
                "Failed to parse blacklist configuration file from %s",
                path,
            )

    def should_filter_out(self, event: Event) -> bool:
        """Check if an event matches either title or location blacklist."""
        title = event.title or ""
        location = event.location or ""

        # 1. Check title blacklists
        for pattern in self.titles:
            if _matches_pattern(title, pattern):
                logger.info(
                    "FILTERED OUT (Title rule '%s') -> Event: '%s'",
                    pattern,
                    title,
                )
                return True

        # 2. Check location blacklists
        for pattern in self.locations:
            if _matches_pattern(location, pattern):
                logger.info(
                    "FILTERED OUT (Location rule '%s') -> Event: '%s'",
                    pattern,
                    location,
                )
                return True

        return False

    def filter_events(self, events: list[Event]) -> list[Event]:
        """Filter a list of events, keeping only those NOT blacklisted."""
        filtered = [ev for ev in events if not self.should_filter_out(ev)]
        logger.info(
            "Filtered events: %d remaining out of %d initial.",
            len(filtered),
            len(events),
        )
        return filtered
