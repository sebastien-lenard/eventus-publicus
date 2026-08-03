# src/eventus_publicus/readers/event_reader.py
# SPDX-FileCopyrightText: 2026 Sebastien Lenard <sebastien.lenard@gmail.com> and Contributors
# SPDX-License-Identifier: Apache-2.0

"""Module to parse event details from saved HTML source files."""

import json
import logging
from pathlib import Path

from bs4 import BeautifulSoup

from eventus_publicus.providers.base import EventProvider
from eventus_publicus.providers.eventbrite import EventbriteProvider

logger = logging.getLogger(__name__)


def _extract_organizer(item: dict) -> str | None:
    """Extract organizer name from JSON-LD item if available."""
    if "organizer" in item:
        organizer_info = item["organizer"]
        if isinstance(organizer_info, dict) and "name" in organizer_info:
            return organizer_info["name"]
    return None


def _extract_address(item: dict) -> str | None:
    """Extract street address from JSON-LD item if available."""
    if "location" in item:
        address_info = item["location"].get("address", {})
        if "streetAddress" in address_info:
            return address_info["streetAddress"]
    return None


def _extract_prices(item: dict) -> tuple[float | None, float | None]:
    """Extract low and high prices from JSON-LD item if available."""
    if "offers" in item and isinstance(item["offers"], list):
        for offer in item["offers"]:
            if "lowPrice" in offer and "highPrice" in offer:
                return float(offer["lowPrice"]), float(offer["highPrice"])
    return None, None


def parse_event_page_from_html(
    soup: BeautifulSoup,
    provider: EventProvider | None = None,
) -> dict:
    """Parse the BeautifulSoup object and extract details."""
    active_provider = provider or EventbriteProvider()
    full_address = None
    low_price = None
    high_price = None
    organizer = None

    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
            items = data if isinstance(data, list) else [data]
            for item in items:
                organizer = organizer or _extract_organizer(item)
                full_address = full_address or _extract_address(item)
                if not low_price and not high_price:
                    low_price, high_price = _extract_prices(item)
        except (json.JSONDecodeError, TypeError):
            continue

    description_html = ""
    overview_selector = active_provider.get_description_overview_selector()
    overview_div = soup.find(
        "div",
        class_=lambda c: bool(c and overview_selector in c and "summary" in str(c)),
    )
    if overview_div:
        description_html = "".join(str(child) for child in overview_div.contents)

    return {
        "organizer": organizer,
        "full_address": full_address,
        "low_price": low_price,
        "high_price": high_price,
        "description": description_html,
    }


def parse_event_page(
    html_file_path: Path,
    provider: EventProvider | None = None,
) -> dict:
    """Parse the HTML file and extract address, prices, description."""
    html_content = html_file_path.read_text(encoding="utf-8")
    soup = BeautifulSoup(html_content, "html.parser")
    return parse_event_page_from_html(soup, provider=provider)


def main() -> None:
    """Execute the parser against the target test data file and output findings."""
    current_dir = Path(__file__).resolve().parent
    project_root = current_dir.parent.parent.parent
    file_subpath = (
        "tests/data/view-source_https___www.eventbrite.ca_e_"
        "la-elegancia-latina-summer-vibes-tickets-1993233171071_"
        "aff=ebdssbdestsearch.html"
    )
    html_file = project_root / file_subpath

    if not html_file.exists():
        logger.error("Error: Target file not found at %s", html_file)
        return

    event_info = parse_event_page(html_file)

    for key, value in event_info.items():
        logger.info("--- %s ---", key)
        logger.info("%s\n", value)


if __name__ == "__main__":
    main()
