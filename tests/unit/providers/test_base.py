# tests/unit/providers/test_base.py
# SPDX-FileCopyrightText: 2026 Sebastien Lenard <sebastien.lenard@gmail.com> and Contributors
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for the event provider base protocol module."""

from pathlib import Path

from bs4 import Tag
from playwright.async_api import Page

from eventus_publicus.providers.base import EventProvider
from eventus_publicus.schemas.event import Event
from eventus_publicus.utils.config import AppConfig


class DummyProvider:
    """A concrete implementation conforming to the EventProvider protocol."""

    name: str = "dummy"

    def is_allowed_domain(self, domain: str) -> bool:
        """Validate domain."""
        return domain == "dummy.com"

    def load_provider_config(self) -> dict:
        """Load config."""
        return {}

    async def smart_wait_for_page(
        self,
        _page: Page,
        _url: str,
        _config: AppConfig | None = None,
    ) -> None:
        """Smart wait."""

    def build_event_list_url(self, page_number: int, date: str) -> str:
        """Build URL."""
        return f"https://dummy.com/events?page={page_number}&date={date}"

    def get_temporary_directory(self, _config: AppConfig | None = None) -> Path:
        """Get temp dir."""
        return Path("dummy_dir")

    def get_cache_file_path(
        self,
        _date_str: str,
        _location: str = "calgary",
        _config: AppConfig | None = None,
    ) -> Path:
        """Get cache path."""
        return Path("dummy_dir/cache.cache")

    def get_report_filenames(
        self,
        _location: str = "calgary",
        _config: AppConfig | None = None,
    ) -> tuple[str, str]:
        """Get report filenames."""
        return ("report.md", "report.html")

    def get_description_overview_selector(self) -> str:
        """Get description selector."""
        return ".description"

    def check_search_status(self, text_content: str) -> bool:
        """Check search status."""
        return "no events" in text_content.lower()

    def get_pagination_selector(self) -> str:
        """Get pagination selector."""
        return ".pagination"

    def get_event_list_card_selectors(self) -> tuple[str, str]:
        """Get list and card selectors."""
        return (".container", ".card")

    def parse_event_card(
        self,
        _card: Tag,
        _event_date: str | None = None,
    ) -> Event | None:
        """Parse card."""
        return None


def test_event_provider_protocol_runtime_checkable() -> None:
    """Verify that a conforming class is recognized as an EventProvider instance."""
    provider = DummyProvider()
    assert isinstance(provider, EventProvider)


def test_dummy_provider_methods() -> None:
    """Verify all protocol methods on a conforming implementation execute correctly."""
    provider = DummyProvider()
    assert provider.name == "dummy"
    assert provider.is_allowed_domain("dummy.com") is True
    assert provider.is_allowed_domain("other.com") is False
    assert provider.load_provider_config() == {}
    assert (
        provider.build_event_list_url(1, "2026-08-01")
        == "https://dummy.com/events?page=1&date=2026-08-01"
    )
    assert provider.get_temporary_directory() == Path("dummy_dir")
    assert provider.get_cache_file_path("2026-08-01") == Path(
        "dummy_dir/cache.cache",
    )
    assert provider.get_report_filenames() == ("report.md", "report.html")
    assert provider.get_description_overview_selector() == ".description"
    assert provider.check_search_status("Sorry, no events found.") is True
    assert provider.get_pagination_selector() == ".pagination"
    assert provider.get_event_list_card_selectors() == (".container", ".card")
    assert provider.parse_event_card(Tag(name="div")) is None
