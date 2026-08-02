# src/eventus-publicus/providers/eventbrite.py
# SPDX-FileCopyrightText: 2026 Sebastien Lenard <sebastien.lenard@gmail.com> and Contributors
# SPDX-License-Identifier: Apache-2.0

"""Provides specific configurations, selectors, and helper functions for Eventbrite."""

import json
import re
import tempfile
from contextlib import suppress
from pathlib import Path

from playwright.async_api import Page
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from eventus_publicus.utils.config import AppConfig, get_config

PROVIDER_NAME = "eventbrite"

URL_BASE = "https://www.eventbrite.ca"
URL_PATH = "/d/canada--calgary/all-events/"


def is_allowed_domain(domain: str) -> bool:
    """Validate if the domain belongs to Eventbrite."""
    if not domain:
        return False
    return any(
        allowed in domain.lower() for allowed in ["eventbrite.ca", "eventbrite.com"]
    )


async def smart_wait_for_page(
    page: Page,
    url: str,
    config: AppConfig | None = None,
) -> None:
    """Execute smart wait using resilient substring CSS selectors based on page type."""
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
                "li[class*='Pagination-module__search-pagination__"
                "navigation-minimal']",
                timeout=timeout,
            )


def get_temporary_directory(config: AppConfig | None = None) -> Path:
    """Return the platform-specific temporary directory path for Eventbrite data."""
    cfg = config or get_config()
    subfolder_pattern = cfg.tmp_subfolder
    folder_name = subfolder_pattern.format(provider=PROVIDER_NAME)
    tmp_dir = Path(tempfile.gettempdir()) / folder_name
    tmp_dir.mkdir(parents=True, exist_ok=True)
    return tmp_dir


def get_description_overview_selector() -> str:
    """Return the CSS selector to locate the event description overview block."""
    return "div[class*='Overview-module-scss-module__']"


def check_search_status(text_content: str) -> bool:
    """Check if the page indicates zero search results."""
    return "Nothing matched your search" in text_content


def get_pagination_selector() -> str:
    """Return the CSS selector for the search pagination element."""
    return "li[class*='Pagination-module__search-pagination__navigation-minimal']"


def get_event_list_card_selectors() -> tuple[str, str]:
    """Return CSS selectors for the event list container and individual event cards."""
    container_selector = (
        "ul[class*='SearchResultPanelContentEventCardList-module__eventList']"
    )
    card_selector = (
        "div[class*='SearchResultPanelContentEventCardList-"
        "module__map_experiment_event_card']"
    )
    return container_selector, card_selector


def get_cache_file_path(
    date_str: str,
    location: str = "calgary",
    config: AppConfig | None = None,
) -> Path:
    """Construct and return the accumulated JSON cache file path for date/location."""
    tmp_dir = get_temporary_directory(config=config)
    return tmp_dir / f"events-{location}-{date_str}-accumulated.json"


def build_event_list_url(page_number: int, date: str) -> str:
    """Construct and return the event listing search URL."""
    return f"{URL_BASE}{URL_PATH}?page={page_number}&start_date={date}&end_date={date}"


def get_report_filenames(
    location: str = "calgary",
    config: AppConfig | None = None,
) -> tuple[str, str]:
    """Return default filenames for Markdown and HTML event reports."""
    cfg = config or get_config()
    template = cfg.output_filename
    md_filename = template.format(
        provider=PROVIDER_NAME,
        location=location,
        ext="md",
    )
    html_filename = template.format(
        provider=PROVIDER_NAME,
        location=location,
        ext="html",
    )
    return md_filename, html_filename


def load_eventbrite_config(_config: AppConfig | None = None) -> dict:
    """Load and parse eventbrite.jsonc configuration file supporting JSONC comments."""
    current_dir = Path(__file__).resolve().parent
    project_root = current_dir.parent.parent.parent
    config_path = project_root / "config" / "eventbrite.jsonc"

    if not config_path.exists():
        return {}

    try:
        content = config_path.read_text(encoding="utf-8")
        # Strip C-style comments (// ...) and block comments (/* ... */)
        content_cleaned = re.sub(r"^\s*//.*$", "", content, flags=re.MULTILINE)
        content_cleaned = re.sub(
            r"/\*.*?\*/",
            "",
            content_cleaned,
            flags=re.DOTALL,
        )
        return json.loads(content_cleaned)
    except (OSError, json.JSONDecodeError, ValueError):
        return {}
