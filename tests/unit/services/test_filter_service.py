# tests/unit/services/test_filter_service.py
# SPDX-FileCopyrightText: 2026 Sebastien Lenard <sebastien.lenard@gmail.com> and Contributors
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for the filter service module."""

from unittest.mock import MagicMock, patch

import pytest

from eventus_publicus.schemas.event import Event
from eventus_publicus.services.filter_service import (
    EventFilterService,
    _matches_pattern,
    _normalize,
)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("", ""),
        ("Hello·World-Test—Pipe|Bar", "hello world test pipe bar"),
        ("  Multiple   Spaces  ", "multiple spaces"),
    ],
)
def test_normalize(text: str, expected: str) -> None:
    """Verify text normalization replaces separators and normalizes."""
    assert _normalize(text) == expected


@pytest.mark.parametrize(
    ("text", "pattern", "expected"),
    [
        ("Summer Music Festival", "Music", True),
        ("Summer Music Festival", "Jazz", False),
        ("Summer Music Festival", "", False),
        ("Summer Music Festival", "*Music*", True),
        ("Summer Music Festival", "Summer*Festival", True),
        ("Summer Music Festival", "Festival*Summer", False),
        ("Any Text", "*", True),
    ],
)
def test_matches_pattern(text: str, pattern: str, expected: bool) -> None:
    """Verify pattern matching handles exact matches, substrings, and wildcards."""
    assert _matches_pattern(text, pattern) == expected


def test_filter_service_load_config_success() -> None:
    """Verify EventFilterService successfully loads blacklists from provider config."""
    mock_provider = MagicMock()
    mock_provider.name = "eventbrite"
    mock_provider.load_provider_config.return_value = {
        "blacklists": {
            "titles": ["Spam Title"],
            "locations": ["Spam Location"],
        },
    }

    with patch("pathlib.Path.exists", return_value=True):
        service = EventFilterService(provider=mock_provider)
        assert service.titles == ["Spam Title"]
        assert service.locations == ["Spam Location"]


def test_filter_service_load_config_missing_file() -> None:
    """Verify EventFilterService initializes empty lists when no config path."""
    mock_provider = MagicMock()
    mock_provider.name = "eventbrite"

    with patch("pathlib.Path.exists", return_value=False):
        service = EventFilterService(provider=mock_provider)
        assert service.titles == []
        assert service.locations == []


def test_filter_service_load_config_exception() -> None:
    """Verify EventFilterService catches exceptions during config loading/validation."""
    mock_provider = MagicMock()
    mock_provider.name = "eventbrite"
    mock_provider.load_provider_config.side_effect = Exception("Invalid config")

    with patch("pathlib.Path.exists", return_value=True):
        service = EventFilterService(provider=mock_provider)
        assert service.titles == []
        assert service.locations == []


def test_filter_service_should_filter_out() -> None:
    """Verify should_filter_out identifies blacklisted titles and locations."""
    mock_provider = MagicMock()
    mock_provider.name = "eventbrite"
    mock_provider.load_provider_config.return_value = {
        "blacklists": {
            "titles": ["Bad Title"],
            "locations": ["Bad Location"],
        },
    }

    with patch("pathlib.Path.exists", return_value=True):
        service = EventFilterService(provider=mock_provider)

        ev_title = Event(
            date="2026-08-01",
            time="19:00",
            title="Bad Title Event",
            link="https://example.com/1",
        )
        ev_loc = Event(
            date="2026-08-01",
            time="19:00",
            title="Good Title",
            location="Bad Location Venue",
            link="https://example.com/2",
        )
        ev_clean = Event(
            date="2026-08-01",
            time="19:00",
            title="Clean Title",
            location="Clean Location",
            link="https://example.com/3",
        )

        assert service.should_filter_out(ev_title) is True
        assert service.should_filter_out(ev_loc) is True
        assert service.should_filter_out(ev_clean) is False

        filtered = service.filter_events([ev_title, ev_loc, ev_clean])
        assert filtered == [ev_clean]
