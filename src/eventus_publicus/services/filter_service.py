# src/eventus-publicus/services/filter_service.py
# SPDX-FileCopyrightText: 2026 Sebastien Lenard <sebastien.lenard@gmail.com> and Contributors
# SPDX-License-Identifier: Apache-2.0
"""Service to load blacklists and filter events by title and location."""

import logging
import re
from pathlib import Path

from pydantic import BaseModel, Field

from eventus_publicus.providers.eventbrite import load_eventbrite_config
from eventus_publicus.schemas.event import Event
from eventus_publicus.utils.config import AppConfig

logger = logging.getLogger(__name__)


class BlacklistConfig(BaseModel):
    """Pydantic model representing external blacklist rules."""

    titles: list[str] = Field(default_factory=list)
    locations: list[str] = Field(default_factory=list)


class ProviderConfig(BaseModel):
    """Pydantic model representing Eventbrite provider configuration."""

    blacklists: BlacklistConfig = Field(default_factory=BlacklistConfig)


def _normalize(text: str) -> str:
    """Normalize text for bulletproof comparison."""
    if not text:
        return ""

    normalized = re.sub(r"[·\-\—\|]", " ", text)
    return re.sub(r"\s+", " ", normalized.lower()).strip()


def _matches_pattern(text: str, pattern: str) -> bool:
    """Check if normalized text matches a wildcard pattern containing '*'."""
    norm_text = _normalize(text)
    norm_pattern = _normalize(pattern)

    if not norm_pattern:
        return False

    if "*" not in norm_pattern:
        return norm_pattern in norm_text

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

    def __init__(self, config: AppConfig | None = None) -> None:
        self.config = config
        self.titles: list[str] = []
        self.locations: list[str] = []

        self._load_config()

    def _load_config(self) -> None:
        """Load and compile blacklists from eventbrite provider config."""
        current_dir = Path(__file__).resolve().parent
        config_path = current_dir.parent.parent.parent / "config" / "eventbrite.jsonc"

        if not config_path.exists():
            logger.warning(
                "Blacklist config not found at %s. No filtering will occur.",
                config_path,
            )
            return

        try:
            raw_data = load_eventbrite_config()
            provider_config = ProviderConfig.model_validate(raw_data)

            self.titles = provider_config.blacklists.titles
            self.locations = provider_config.blacklists.locations
            logger.info(
                "Loaded %d title rules and %d location rules from blacklist config.",
                len(self.titles),
                len(self.locations),
            )
        except Exception:
            logger.exception(
                "Failed to parse blacklist configuration file from %s",
                config_path,
            )

    def should_filter_out(self, event: Event) -> bool:
        """Check if an event matches either title or location blacklist."""
        title = event.title or ""
        location = event.location or ""

        for pattern in self.titles:
            if _matches_pattern(title, pattern):
                logger.info(
                    "FILTERED OUT (Title rule '%s') -> Event: '%s'",
                    pattern,
                    title,
                )
                return True

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
