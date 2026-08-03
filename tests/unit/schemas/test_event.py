# tests/unit/schemas/test_event.py
# SPDX-FileCopyrightText: 2026 Sebastien Lenard <sebastien.lenard@gmail.com> and Contributors
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for the Event pydantic schema module."""

import pytest

from eventus_publicus.schemas.event import Event


@pytest.mark.parametrize(
    ("raw_time", "expected_normalized"),
    [
        ("11:30 AM", "11:30"),
        ("12:00 PM", "12:00"),
        ("12:00 AM", "00:00"),
        ("12:30 AM", "00:30"),
        ("7:30PM", "19:30"),
        ("9 AM", "09:00"),
        ("18:30", "18:30"),
        ("09:15", "09:15"),
        ("Unknown", "23:59"),
        ("", "23:59"),
        ("unrecognized-format", "unrecognized-format"),
    ],
)
def test_event_time_normalization(raw_time: str, expected_normalized: str) -> None:
    """Verify normalize_time validator correctly converts AM/PM and 24h formats."""
    event = Event(
        date="2026-08-01",
        time=raw_time,
        title="Test Event",
        link="https://example.com",
    )
    assert event.time == expected_normalized


def test_event_default_fields() -> None:
    """Verify Event schema default values for optional fields."""
    event = Event(
        date="2026-08-01",
        time="10:00",
        title="Minimal Event",
        link="https://example.com",
    )
    assert event.location == "Unknown"
    assert event.organizer is None
    assert event.low_price is None
    assert event.high_price is None
    assert event.full_address is None
    assert event.description == ""


def test_unique_identity_with_link() -> None:
    """Verify unique_identity property cleans query parameters and anchors from link."""
    event = Event(
        date="2026-08-01",
        time="10:00",
        title="Event",
        link="https://example.com/page?query=1#anchor",
    )
    assert event.unique_identity == "https://example.com/page"


def test_unique_identity_fallback_without_link() -> None:
    """Verify unique_identity falls back to compound key when link is empty."""
    event = Event(
        date="2026-08-01",
        time="10:00",
        location="Calgary Hall",
        title="Fallback Event",
        link="",
    )
    assert event.unique_identity == "2026-08-01|10:00|calgary hall|fallback event"
