# src/eventus-publicus/providers/eventbrite.py
# SPDX-FileCopyrightText: 2026 Sebastien Lenard <sebastien.lenard@gmail.com> and Contributors
# SPDX-License-Identifier: Apache-2.0
"""Provides specific configurations, selectors, and helper functions for Eventbrite."""

import json
import re
import tempfile
from contextlib import suppress
from pathlib import Path

from bs4 import Tag
from playwright.async_api import Page
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from eventus_publicus.schemas.event import Event
from eventus_publicus.utils.config import AppConfig, get_config

PROVIDER_NAME = "eventbrite"
URL_BASE = "https://www.eventbrite.ca"
URL_PATH = "/d/canada--calgary/all-events/"


class EventbriteProvider:
    """Concrete provider implementing Eventbrite functionality."""

    def __init__(self) -> None:
        self.name = PROVIDER_NAME

    def is_allowed_domain(self, domain: str) -> bool:
        """Validate if the domain belongs to Eventbrite using a secure regex."""
        if not domain:
            return False
        # Ensures eventbrite is the root domain with valid TLDs/ccSLDs
        pattern = (
            r"^(?:[a-zA-Z0-9-]+\.)*eventbrite\.(?:com|ca|co\.uk|com\.au|"
            r"[a-z]{2}(?:\.[a-z]{2})?)$"
        )
        return bool(re.match(pattern, domain.lower()))

    async def smart_wait_for_page(
        self,
        page: Page,
        url: str,
        config: AppConfig | None = None,
    ) -> None:
        """Execute smart wait using resilient substring CSS selectors."""
        cfg = config or get_config()
        timeout = cfg.playwright_wait_timeout_ms

        if "/e/" in url:
            with suppress(PlaywrightTimeoutError):
                await page.wait_for_selector(
                    "div[class*='Overview-module-scss-module__'][class*='summary']",
                    timeout=timeout,
                )
        else:
            with suppress(PlaywrightTimeoutError):
                await page.wait_for_selector(
                    "ul[class*='SearchResultPanelContentEventCardList-"
                    "module__'], "
                    "li[class*='Pagination-module__search-pagination"
                    "__navigation-minimal']",
                    timeout=timeout,
                )

    def get_temporary_directory(
        self,
        config: AppConfig | None = None,
    ) -> Path:
        """Return temporary directory path for Eventbrite data."""
        cfg = config or get_config()
        subfolder_pattern = cfg.tmp_subfolder
        folder_name = subfolder_pattern.format(provider=self.name)
        tmp_dir = Path(tempfile.gettempdir()) / folder_name
        tmp_dir.mkdir(parents=True, exist_ok=True)
        return tmp_dir

    def get_description_overview_selector(self) -> str:
        """Return CSS selector for description overview block."""
        return "div[class*='Overview-module-scss-module__']"

    def check_search_status(self, text_content: str) -> bool:
        """Check if page indicates zero search results."""
        return "Nothing matched your search" in text_content

    def get_pagination_selector(self) -> str:
        """Return CSS selector for search pagination element."""
        return "li[class*='Pagination-module__search-pagination__navigation-minimal']"

    def get_event_list_card_selectors(self) -> tuple[str, str]:
        """Return CSS selectors for event list container and cards."""
        container_selector = (
            "ul[class*='SearchResultPanelContentEventCardList-module__eventList']"
        )
        card_selector = (
            "div[class*='SearchResultPanelContentEventCardList"
            "-module__map_experiment_event_card']"
        )
        return container_selector, card_selector

    def get_cache_file_path(
        self,
        date_str: str,
        location: str = "calgary",
        config: AppConfig | None = None,
    ) -> Path:
        """Construct and return accumulated JSON cache file path."""
        tmp_dir = self.get_temporary_directory(config=config)
        return tmp_dir / f"events-{location}-{date_str}-accumulated.json"

    def build_event_list_url(self, page_number: int, date: str) -> str:
        """Construct and return event listing search URL."""
        return (
            f"{URL_BASE}{URL_PATH}?page={page_number}&start_date={date}&end_date={date}"
        )

    def get_report_filenames(
        self,
        location: str = "calgary",
        config: AppConfig | None = None,
    ) -> tuple[str, str]:
        """Return default filenames for Markdown and HTML reports."""
        cfg = config or get_config()
        template = cfg.output_filename
        md_filename = template.format(
            provider=self.name,
            location=location,
            ext="md",
        )
        html_filename = template.format(
            provider=self.name,
            location=location,
            ext="html",
        )
        return md_filename, html_filename

    def load_provider_config(
        self,
        _config: AppConfig | None = None,
    ) -> dict:
        """Load and parse eventbrite.jsonc configuration file."""
        current_dir = Path(__file__).resolve().parent
        project_root = current_dir.parent.parent.parent
        config_path = project_root / "config" / "eventbrite.jsonc"

        if not config_path.exists():
            return {}

        try:
            content = config_path.read_text(encoding="utf-8")
            content_cleaned = re.sub(
                r"^\s*//.*$",
                "",
                content,
                flags=re.MULTILINE,
            )
            content_cleaned = re.sub(
                r"/\*.*?\*/",
                "",
                content_cleaned,
                flags=re.DOTALL,
            )
            return json.loads(content_cleaned)
        except (OSError, json.JSONDecodeError, ValueError):
            return {}

    def parse_event_card(
        self,
        card: Tag,
        event_date: str | None = None,
    ) -> Event | None:
        """Extract event details from a single event card element."""
        try:
            first_a = card.find("a")
            link = first_a.get("href", "") if isinstance(first_a, Tag) else ""
            if isinstance(link, list):
                link = link[0] if link else ""

            first_h3 = card.find("h3")
            title = first_h3.get_text(strip=True) if first_h3 else "Unknown"

            time_text = ""
            location_text = ""
            p_tags = card.find_all("p")
            time_pattern = re.compile(
                r"\b\d{1,2}(?:\:\d{2})?\s*(?:AM|PM)\b",
                re.IGNORECASE,
            )

            for i, p in enumerate(p_tags):
                text = p.get_text(strip=True)
                match = time_pattern.search(text)
                if match:
                    time_text = match.group(0).strip()
                    if i + 1 < len(p_tags):
                        location_text = p_tags[i + 1].get_text(strip=True)
                    break

            return Event(
                date=event_date or "Unknown",
                time=time_text or "Unknown",
                location=location_text or "Unknown",
                title=title,
                link=str(link),
            )
        except (AttributeError, KeyError, TypeError, ValueError, IndexError):
            return None
