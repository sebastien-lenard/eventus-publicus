# tests/unit/providers/test_eventbrite.py
# SPDX-FileCopyrightText: 2026 Sebastien Lenard <sebastien.lenard@gmail.com> and Contributors
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for the Eventbrite provider module."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from bs4 import BeautifulSoup, Tag
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from eventus_publicus.providers.eventbrite import EventbriteProvider


def test_eventbrite_init() -> None:
    """Verify EventbriteProvider initializes with correct name."""
    provider = EventbriteProvider()
    assert provider.name == "eventbrite"


@pytest.mark.parametrize(
    ("domain", "expected"),
    [
        ("www.eventbrite.com", True),
        ("eventbrite.ca", True),
        ("sub.eventbrite.co.uk", True),
        ("eventbrite.com.au", True),
        ("evil.com", False),
        ("eventbrite.fake", False),
        ("", False),
    ],
)
def test_is_allowed_domain(domain: str, expected: bool) -> None:
    """Verify domain validation regex identifies allowed Eventbrite domains."""
    provider = EventbriteProvider()
    assert provider.is_allowed_domain(domain) == expected


@pytest.mark.asyncio
async def test_smart_wait_for_page_event_detail() -> None:
    """Verify smart_wait_for_page waits for page selector when '/e/' is in URL."""
    provider = EventbriteProvider()
    mock_page = AsyncMock()
    mock_page.wait_for_selector = AsyncMock()

    await provider.smart_wait_for_page(
        mock_page,
        "https://www.eventbrite.ca/e/cool-event-123",
    )
    mock_page.wait_for_selector.assert_awaited_once()


@pytest.mark.asyncio
async def test_smart_wait_for_page_event_list() -> None:
    """Verify smart_wait_for_page waits for list selectors when '/e/' is absent."""
    provider = EventbriteProvider()
    mock_page = AsyncMock()
    mock_page.wait_for_selector = AsyncMock()

    await provider.smart_wait_for_page(
        mock_page,
        "https://www.eventbrite.ca/d/canada--calgary/all-events/",
    )
    mock_page.wait_for_selector.assert_awaited_once()


@pytest.mark.asyncio
async def test_smart_wait_for_page_timeout_suppressed() -> None:
    """Verify smart_wait_for_page suppresses PlaywrightTimeoutError."""
    provider = EventbriteProvider()
    mock_page = AsyncMock()
    mock_page.wait_for_selector = AsyncMock(
        side_effect=PlaywrightTimeoutError("Timeout"),
    )

    # Should not raise
    await provider.smart_wait_for_page(
        mock_page,
        "https://www.eventbrite.ca/e/timeout-event",
    )


def test_get_temporary_directory(tmp_path: Path) -> None:
    """Verify get_temporary_directory creates and returns correct path."""
    provider = EventbriteProvider()
    mock_config = MagicMock()
    mock_config.tmp_subfolder = "test_sub_{provider}"

    with patch("tempfile.gettempdir", return_value=str(tmp_path)):
        tmp_dir = provider.get_temporary_directory(config=mock_config)
        assert tmp_dir.exists()
        assert tmp_dir.name == "test_sub_eventbrite"


def test_get_selectors_and_statuses() -> None:
    """Verify selector and status checking helper methods."""
    provider = EventbriteProvider()
    assert "Overview" in provider.get_description_overview_selector()
    assert provider.check_search_status("Nothing matched your search") is True
    assert provider.check_search_status("Events found") is False
    assert "Pagination" in provider.get_pagination_selector()

    container_sel, card_sel = provider.get_event_list_card_selectors()
    assert "eventList" in container_sel
    assert "event_card" in card_sel


def test_get_cache_file_path(tmp_path: Path) -> None:
    """Verify cache file path construction."""
    provider = EventbriteProvider()
    mock_config = MagicMock()
    mock_config.tmp_subfolder = "cache_{provider}"

    with patch("tempfile.gettempdir", return_value=str(tmp_path)):
        cache_path = provider.get_cache_file_path(
            "2026-08-01",
            location="calgary",
            config=mock_config,
        )
        assert cache_path.name == "events-calgary-2026-08-01-accumulated.json"


def test_build_event_list_url() -> None:
    """Verify listing search URL builder."""
    provider = EventbriteProvider()
    url = provider.build_event_list_url(2, "2026-08-01")
    assert "page=2" in url
    assert "start_date=2026-08-01" in url
    assert "end_date=2026-08-01" in url


def test_get_report_filenames() -> None:
    """Verify report filename formatting."""
    provider = EventbriteProvider()
    mock_config = MagicMock()
    mock_config.output_filename = "{provider}-{location}.{ext}"

    md_file, html_file = provider.get_report_filenames(
        location="calgary",
        config=mock_config,
    )
    assert md_file == "eventbrite-calgary.md"
    assert html_file == "eventbrite-calgary.html"


def test_load_provider_config_missing_file() -> None:
    """Verify load_provider_config returns empty dict when config file is missing."""
    provider = EventbriteProvider()
    with patch("pathlib.Path.exists", return_value=False):
        assert provider.load_provider_config() == {}


def test_load_provider_config_parsing(tmp_path: Path) -> None:
    """Verify JSONC parsing logic directly."""
    provider = EventbriteProvider()
    jsonc_file = tmp_path / "eventbrite.jsonc"
    jsonc_file.write_text(
        '// Header comment\n{"key": "value" /* inline comment */}',
        encoding="utf-8",
    )

    with (
        patch("pathlib.Path.exists", return_value=True),
        patch(
            "pathlib.Path.read_text",
            return_value=jsonc_file.read_text(encoding="utf-8"),
        ),
    ):
        cfg = provider.load_provider_config()
        assert cfg == {"key": "value"}


def test_load_provider_config_exception(tmp_path: Path) -> None:
    """Verify load_provider_config handles read/json errors gracefully."""
    provider = EventbriteProvider()
    with (
        patch("pathlib.Path.exists", return_value=True),
        patch(
            "pathlib.Path.read_text",
            side_effect=OSError("Read error"),
        ),
    ):
        assert provider.load_provider_config() == {}


def test_parse_event_card_success() -> None:
    """Verify parse_event_card successfully extracts event info from card HTML."""
    provider = EventbriteProvider()
    html_card = """
    <div>
        <a href="https://www.eventbrite.ca/e/test-event-123">Link</a>
        <h3>Amazing Concert</h3>
        <p>Some intro text</p>
        <p>7:00 PM</p>
        <p>Venue Location Calgary</p>
    </div>
    """
    soup = BeautifulSoup(html_card, "html.parser")
    card = soup.div
    assert isinstance(card, Tag)

    event = provider.parse_event_card(card, event_date="2026-08-01")
    assert event is not None
    assert event.date == "2026-08-01"
    assert event.title == "Amazing Concert"
    assert event.time == "19:00"
    assert event.location == "Venue Location Calgary"
    assert event.link == "https://www.eventbrite.ca/e/test-event-123"


def test_parse_event_card_href_as_list() -> None:
    """Verify parse_event_card handles href attribute being a list (non-empty/empty)."""
    provider = EventbriteProvider()
    card = Tag(name="div")

    mock_a = MagicMock(spec=Tag)
    mock_a.get.return_value = ["https://example.com/list-link"]

    with patch.object(
        card,
        "find",
        side_effect=lambda tag: mock_a if tag == "a" else None,
    ):
        event = provider.parse_event_card(card, event_date="2026-08-01")
        assert event is not None
        assert event.link == "https://example.com/list-link"

    # Empty list case
    mock_a.get.return_value = []
    with patch.object(
        card,
        "find",
        side_effect=lambda tag: mock_a if tag == "a" else None,
    ):
        event = provider.parse_event_card(card, event_date="2026-08-01")
        assert event is not None
        assert event.link == ""


def test_parse_event_card_exception() -> None:
    """Verify parse_event_card returns None on parsing failure."""
    provider = EventbriteProvider()
    mock_card = MagicMock()
    mock_card.find.side_effect = AttributeError("Missing")

    assert provider.parse_event_card(mock_card) is None


def test_build_event_list_url_with_country() -> None:
    """Verify listing search URL builder includes country when provided."""
    provider = EventbriteProvider()
    url = provider.build_event_list_url(
        1,
        "2026-08-01",
        country="United States",
        city="New York",
    )
    assert "united-states--new-york" in url
    assert "page=1" in url
    assert "start_date=2026-08-01" in url
    assert "end_date=2026-08-01" in url
