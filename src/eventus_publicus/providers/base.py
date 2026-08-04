# src/eventus_publicus/providers/base.py
# SPDX-FileCopyrightText: 2026 Sebastien Lenard <sebastien.lenard@gmail.com> and Contributors
# SPDX-License-Identifier: Apache-2.0
"""Abstract protocol defining the contract for all event providers."""

from pathlib import Path
from typing import Protocol, runtime_checkable

from bs4 import Tag
from playwright.async_api import Page

from eventus_publicus.schemas.event import Event
from eventus_publicus.utils.config import AppConfig


@runtime_checkable
class EventProvider(Protocol):
    """Protocol that every event provider must implement."""

    name: str

    def is_allowed_domain(self, domain: str) -> bool:
        """Validate if the domain belongs to this provider."""
        ...

    def load_provider_config(self) -> dict:
        """Load provider-specific configuration/blacklist settings."""
        ...

    async def smart_wait_for_page(
        self,
        page: Page,
        url: str,
        config: AppConfig | None = None,
    ) -> None:
        """Execute provider-specific smart waits after page navigation."""
        ...

    def build_event_list_url(
        self,
        page_number: int,
        date: str,
        country: str | None = None,
        city: str = "calgary",
    ) -> str:
        """Construct and return the search listing URL."""
        ...

    def get_temporary_directory(self, config: AppConfig | None = None) -> Path:
        """Return the platform-specific temporary directory path."""
        ...

    def get_cache_file_path(
        self,
        date_str: str,
        location: str = "calgary",
        config: AppConfig | None = None,
    ) -> Path:
        """Return the cache file path for accumulated date results."""
        ...

    def get_report_filenames(
        self,
        location: str = "calgary",
        config: AppConfig | None = None,
    ) -> tuple[str, str]:
        """Return default filenames for Markdown and HTML event reports."""
        ...

    def get_description_overview_selector(self) -> str:
        """Return the CSS selector for the description overview block."""
        ...

    def check_search_status(self, text_content: str) -> bool:
        """Check if the page indicates zero search results or invalid location."""
        ...

    def get_pagination_selector(self) -> str:
        """Return the CSS selector for search pagination."""
        ...

    def get_event_list_card_selectors(self) -> tuple[str, str]:
        """Return CSS selectors for the event list container and cards."""
        ...

    def parse_event_card(
        self,
        card: Tag,
        event_date: str | None = None,
    ) -> Event | None:
        """Extract event details from a provider-specific card element."""
        ...
