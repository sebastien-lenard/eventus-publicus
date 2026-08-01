# src/eventus-publicus/schemas/event.py
# SPDX-FileCopyrightText: 2026 Sebastien Lenard <sebastien.lenard@gmail.com> and Contributors
# SPDX-License-Identifier: Apache-2.0
"""Pydantic data model for events."""

import re
from typing import Annotated

from pydantic import BaseModel, Field, field_validator

HOURS_IN_HALF_DAY = 12


class Event(BaseModel):
    """Structured representation of an event with validation."""

    date: str = Field(..., description="Event date in YYYY-MM-DD format")
    time: str = Field(..., description="Event start time (normalized to 24h HH:MM)")
    title: str = Field(..., description="Event title")
    link: str = Field(..., description="Event ticket/web page URL")

    # Optional / enriched fields defaulting to None or empty strings
    location: Annotated[str, Field(description="Listing location summary")] = "Unknown"
    organizer: Annotated[
        str | None,
        Field(description="Event organizer name"),
    ] = None
    low_price: Annotated[
        float | None,
        Field(description="Lowest ticket price"),
    ] = None
    high_price: Annotated[
        float | None,
        Field(description="Highest ticket price"),
    ] = None
    full_address: Annotated[
        str | None,
        Field(description="Street address"),
    ] = None
    description: Annotated[
        str,
        Field(description="HTML event summary/description"),
    ] = ""

    @field_validator("time", mode="before")
    @classmethod
    def normalize_time(cls, value: str) -> str:
        """Parse raw time strings (AM/PM or 24-hour) and convert to 24-hour format."""
        if not value or not isinstance(value, str) or value == "Unknown":
            return "23:59"  # Push unparsed times to the end

        cleaned = value.strip().upper()

        # 1. Try matching 12-hour format with AM/PM (e.g., "11:00 AM", "7:30PM", "9 AM")
        match_12h = re.search(r"(\d{1,2})(?:\:(\d{2}))?\s*(AM|PM)", cleaned)
        if match_12h:
            hour = int(match_12h.group(1))
            minute = int(match_12h.group(2)) if match_12h.group(2) else 0
            meridiem = match_12h.group(3)

            if meridiem == "PM" and hour < HOURS_IN_HALF_DAY:
                hour += HOURS_IN_HALF_DAY
            elif meridiem == "AM" and hour == HOURS_IN_HALF_DAY:
                hour = 0

            return f"{hour:02d}:{minute:02d}"

        # 2. Try matching 24-hour format (e.g., "18:30", "09:15", "23:00")
        match_24h = re.search(r"\b([01]?\d|2[0-3]):([0-5]\d)\b", cleaned)
        if match_24h:
            hour = int(match_24h.group(1))
            minute = int(match_24h.group(2))
            return f"{hour:02d}:{minute:02d}"

        # Fallback to original string if no patterns match
        return value

    @property
    def unique_identity(self) -> str:
        """Return a robust unique identifier for deduplication.

        Uses the clean link if available; otherwise falls back to a compound
        key of date, time, location, and title.
        """
        if self.link:
            # Strip query parameters and anchors from the URL
            return self.link.split("?")[0].split("#")[0].strip()

        # Compound fallback key
        return f"{self.date}|{self.time}|{self.location}|{self.title}".lower()
