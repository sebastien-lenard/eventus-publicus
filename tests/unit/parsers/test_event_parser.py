# tests/unit/parsers/test_event_parser.py
# SPDX-FileCopyrightText: 2026 Sebastien Lenard <sebastien.lenard@gmail.com> and Contributors
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for the event parser module."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from bs4 import BeautifulSoup

from eventus_publicus.parsers.event_parser import (
    _extract_address,
    _extract_organizer,
    _extract_prices,
    parse_event_page,
    parse_event_page_from_html,
)


@pytest.mark.parametrize(
    ("item", "expected"),
    [
        ({"organizer": {"name": "Test Org"}}, "Test Org"),
        ({"organizer": "Not a dict"}, None),
        ({"organizer": {"no_name": "foo"}}, None),
        ({}, None),
    ],
)
def test_extract_organizer(item: dict, expected: str | None) -> None:
    """Verify organizer extraction handles various JSON structures."""
    assert _extract_organizer(item) == expected


@pytest.mark.parametrize(
    ("item", "expected"),
    [
        (
            {"location": {"address": {"streetAddress": "123 Main St"}}},
            "123 Main St",
        ),
        ({"location": {}}, None),
        ({}, None),
    ],
)
def test_extract_address(item: dict, expected: str | None) -> None:
    """Verify address extraction handles various JSON structures."""
    assert _extract_address(item) == expected


@pytest.mark.parametrize(
    ("item", "expected"),
    [
        ({"offers": [{"lowPrice": "10.0", "highPrice": "20.0"}]}, (10.0, 20.0)),
        ({"offers": [{"lowPrice": "10.0"}]}, (None, None)),
        ({"offers": "not a list"}, (None, None)),
        ({}, (None, None)),
    ],
)
def test_extract_prices(
    item: dict,
    expected: tuple[float | None, float | None],
) -> None:
    """Verify price extraction handles various offer structures."""
    assert _extract_prices(item) == expected


def test_parse_event_page_from_html_full() -> None:
    """Verify parsing event page from HTML with complete JSON-LD and description."""
    html_content = """
    <html>
        <body>
            <script type="application/ld+json">
            {
                "@type": "Event",
                "organizer": {"name": "Latina Vibes"},
                "location": {"address": {"streetAddress": "456 Beach Rd"}},
                "offers": [{"lowPrice": "15", "highPrice": "30"}]
            }
            </script>
            <div class="event-description-summary">
                <p>Great summer vibes event!</p>
            </div>
        </body>
    </html>
    """
    soup = BeautifulSoup(html_content, "html.parser")
    mock_provider = MagicMock()
    mock_provider.get_description_overview_selector.return_value = "event-description"

    result = parse_event_page_from_html(soup, provider=mock_provider)

    assert result["organizer"] == "Latina Vibes"
    assert result["full_address"] == "456 Beach Rd"
    assert result["low_price"] == 15.0
    assert result["high_price"] == 30.0
    assert "Great summer vibes" in result["description"]


def test_parse_event_page_from_html_list_and_invalid_json() -> None:
    """Verify parsing handles JSON-LD lists and recovers from invalid script tags."""
    html_content = """
    <html>
        <body>
            <script type="application/ld+json">
            INVALID JSON CONTENT
            </script>
            <script type="application/ld+json">
            [
                {"organizer": {"name": "Org 1"}},
                {"location": {"address": {"streetAddress": "789 Park Ave"}}}
            ]
            </script>
        </body>
    </html>
    """
    soup = BeautifulSoup(html_content, "html.parser")
    result = parse_event_page_from_html(soup)

    assert result["organizer"] == "Org 1"
    assert result["full_address"] == "789 Park Ave"
    assert result["description"] == ""


def test_parse_event_page_file(tmp_path: Path) -> None:
    """Verify file-based event page parser reads text and delegates parsing."""
    html_file = tmp_path / "event.html"
    html_file.write_text(
        """
        <html>
            <body>
                <script type="application/ld+json">
                {"organizer": {"name": "File Org"}}
                </script>
            </body>
        </html>
        """,
        encoding="utf-8",
    )

    result = parse_event_page(html_file)
    assert result["organizer"] == "File Org"
