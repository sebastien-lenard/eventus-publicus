# tests/unit/parsers/test_list_parser.py
# SPDX-FileCopyrightText: 2026 Sebastien Lenard <sebastien.lenard@gmail.com> and Contributors
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for the event list parser module."""

import logging
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from bs4 import Tag

from eventus_publicus.parsers.list_parser import (
    check_page_status,
    parse_event_card,
    parse_html_events,
    parse_html_events_to_dict,
)
from eventus_publicus.schemas.event import Event


def test_check_page_status_oserror() -> None:
    """Verify check_page_status returns default fallback on file read OSError."""
    non_existent = Path("non_existent_file_9999.html")
    has_no_results, current_page, total_pages = check_page_status(
        non_existent,
    )
    assert has_no_results is False
    assert current_page == 1
    assert total_pages == 1


def test_check_page_status_success_with_pagination(tmp_path: Path) -> None:
    """Verify check_page_status extracts search status and pagination correctly."""
    html_file = tmp_path / "list.html"
    html_file.write_text(
        """
        <html>
            <body>
                <div data-testid="pagination-container">
                    <span data-testid="pagination-string">Page 2 of 5</span>
                </div>
            </body>
        </html>
        """,
        encoding="utf-8",
    )

    mock_provider = MagicMock()
    mock_provider.check_search_status.return_value = True
    mock_provider.get_pagination_selector.return_value = (
        '[data-testid="pagination-container"]'
    )

    has_no_results, current_page, total_pages = check_page_status(
        html_file,
        provider=mock_provider,
    )
    assert has_no_results is True
    assert current_page == 2
    assert total_pages == 5


def test_check_page_status_missing_pagination_elements(tmp_path: Path) -> None:
    """Verify check_page_status handles missing pagination elements."""
    html_file = tmp_path / "list.html"
    html_file.write_text(
        "<html><body><div>No Pagination</div></body></html>",
        encoding="utf-8",
    )

    mock_provider = MagicMock()
    mock_provider.check_search_status.return_value = False
    mock_provider.get_pagination_selector.return_value = ".non-existent"

    has_no_results, current_page, total_pages = check_page_status(
        html_file,
        provider=mock_provider,
    )
    assert has_no_results is False
    assert current_page == 1
    assert total_pages == 1


def test_parse_event_card_success() -> None:
    """Verify parse_event_card returns Event when successful."""
    card = Tag(name="div")
    mock_event = Event(
        date="2026-08-01",
        title="Concert",
        time="19:00",
        location="Calgary",
        link="https://example.com/event",
    )
    mock_provider = MagicMock()
    mock_provider.parse_event_card.return_value = mock_event

    result = parse_event_card(
        card,
        event_date="2026-08-01",
        provider=mock_provider,
    )
    assert result == mock_event


def test_parse_event_card_exception() -> None:
    """Verify parse_event_card catches exceptions and returns None."""
    card = Tag(name="div")
    mock_provider = MagicMock()
    mock_provider.parse_event_card.side_effect = Exception("Parsing error")

    result = parse_event_card(card, provider=mock_provider)
    assert result is None


def test_parse_html_events_file_error() -> None:
    """Verify parse_html_events exits with code 1 on file read OSError."""
    non_existent = Path("non_existent_file_9999.html")
    with pytest.raises(SystemExit) as exc_info:
        parse_html_events(non_existent)
    assert exc_info.value.code == 1


def test_parse_html_events_missing_container(tmp_path: Path) -> None:
    """Verify parse_html_events returns empty list if container is missing."""
    html_file = tmp_path / "list.html"
    html_file.write_text(
        "<html><body><div>No list here</div></body></html>",
        encoding="utf-8",
    )

    mock_provider = MagicMock()
    mock_provider.get_event_list_card_selectors.return_value = (
        "#missing-container",
        ".card",
    )

    events = parse_html_events(html_file, provider=mock_provider)
    assert events == []


def test_parse_html_events_success(tmp_path: Path) -> None:
    """Verify parse_html_events successfully extracts and filters events."""
    html_file = tmp_path / "list.html"
    html_file.write_text(
        """
        <html>
            <body>
                <div id="events-container">
                    <div class="card">Event 1</div>
                    <div class="card">Event 2</div>
                </div>
            </body>
        </html>
        """,
        encoding="utf-8",
    )

    event1 = Event(
        date="2026-08-01",
        title="B Event",
        time="20:00",
        location="Calgary",
        link="https://example.com/1",
    )
    mock_provider = MagicMock()
    mock_provider.get_event_list_card_selectors.return_value = (
        "#events-container",
        ".card",
    )
    mock_provider.parse_event_card.side_effect = [event1, None]

    events = parse_html_events(html_file, provider=mock_provider)
    assert len(events) == 1
    assert events[0].title == "B Event"


def test_parse_html_events_to_dict(tmp_path: Path) -> None:
    """Verify parse_html_events_to_dict sorts events and wraps in dictionary."""
    html_file = tmp_path / "list.html"
    html_file.write_text(
        """
        <html>
            <body>
                <div id="events-container">
                    <div class="card">1</div>
                    <div class="card">2</div>
                </div>
            </body>
        </html>
        """,
        encoding="utf-8",
    )

    event_a = Event(
        date="2026-08-01",
        title="Title A",
        time="18:00",
        location="Calgary",
        link="https://example.com/a",
    )
    event_b = Event(
        date="2026-08-01",
        title="Title B",
        time="18:00",
        location="Calgary",
        link="https://example.com/b",
    )

    mock_provider = MagicMock()
    mock_provider.get_event_list_card_selectors.return_value = (
        "#events-container",
        ".card",
    )
    mock_provider.parse_event_card.side_effect = [event_b, event_a]

    result = parse_html_events_to_dict(html_file, provider=mock_provider)
    assert "events" in result
    assert result["events"][0].title == "Title A"
    assert result["events"][1].title == "Title B"


def test_check_page_status_not_found_warning(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Verify check_page_status logs a warning when the not-found message appears."""
    html_file = tmp_path / "not_found.html"
    html_file.write_text(
        (
            "<html><body>Whoops, the page or event you are looking for "
            "was not found.</body></html>"
        ),
        encoding="utf-8",
    )

    mock_provider = MagicMock()
    mock_provider.check_search_status.return_value = True
    mock_provider.get_pagination_selector.return_value = ".non-existent"

    with caplog.at_level(logging.WARNING):
        has_no_results, current_page, total_pages = check_page_status(
            html_file,
            provider=mock_provider,
        )

    assert has_no_results is True
    assert current_page == 1
    assert total_pages == 1
    assert "Whoops, the page or event you are looking for was not found" in caplog.text
