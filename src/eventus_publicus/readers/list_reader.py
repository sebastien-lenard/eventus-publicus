# src/eventus-publicus/readers/list_reader.py
# SPDX-FileCopyrightText: 2026 Sebastien Lenard <sebastien.lenard@gmail.com> and Contributors
# SPDX-License-Identifier: Apache-2.0
"""Scan HTML event listing and generate structured Event dictionaries."""

import logging
import re
from pathlib import Path

from bs4 import BeautifulSoup, Tag

from eventus_publicus.providers.base import EventProvider
from eventus_publicus.providers.eventbrite import EventbriteProvider
from eventus_publicus.schemas.event import Event

logger = logging.getLogger(__name__)


def check_page_status(
    html_path: Path,
    provider: EventProvider | None = None,
) -> tuple[bool, int, int]:
    """Check if page has no search results and extract pagination info."""
    active_provider = provider or EventbriteProvider()
    try:
        content = html_path.read_text(encoding="utf-8")
    except OSError:
        return False, 1, 1

    soup = BeautifulSoup(content, "html.parser")
    text_content = soup.get_text()

    has_no_results = active_provider.check_search_status(text_content)

    current_page = 1
    total_pages = 1

    pagination_elem = soup.select_one(active_provider.get_pagination_selector())
    if pagination_elem:
        span_elem = pagination_elem.find("span", {"data-testid": "pagination-string"})
        if span_elem:
            full_pagination_text = pagination_elem.get_text(strip=True)
            match = re.search(
                r"(\d+)\s*of\s*(\d+)",
                full_pagination_text,
                re.IGNORECASE,
            )
            if match:
                current_page = int(match.group(1))
                total_pages = int(match.group(2))

    return has_no_results, current_page, total_pages


def parse_event_card(
    card: Tag,
    event_date: str | None = None,
    provider: EventProvider | None = None,
) -> Event | None:
    """Extract event details from a single event card element into an Event."""
    active_provider = provider or EventbriteProvider()
    try:
        return active_provider.parse_event_card(card, event_date=event_date)
    except Exception:
        logger.exception("Failed to parse card")
        return None


def parse_html_events(
    html_path: Path,
    event_date: str | None = None,
    provider: EventProvider | None = None,
) -> list[Event]:
    """Scan HTML file and extract Event objects."""
    active_provider = provider or EventbriteProvider()
    try:
        content = html_path.read_text(encoding="utf-8")
    except OSError:
        logger.exception("Failed to read HTML file")
        raise SystemExit(1) from None

    soup = BeautifulSoup(content, "html.parser")

    container_selector, card_selector = active_provider.get_event_list_card_selectors()
    event_list = soup.select_one(container_selector)

    if not event_list or not isinstance(event_list, Tag):
        logger.warning("Target event list container not found in HTML.")
        return []

    cards = event_list.select(card_selector)

    return [
        ev
        for card in cards
        if isinstance(card, Tag)
        and (
            ev := parse_event_card(
                card,
                event_date=event_date,
                provider=active_provider,
            )
        )
        is not None
    ]


def parse_html_events_to_dict(
    html_path: Path,
    event_date: str | None = None,
    provider: EventProvider | None = None,
) -> dict[str, list[Event]]:
    """Scan HTML file and generate a sorted dictionary containing Events."""
    events = parse_html_events(html_path, event_date=event_date, provider=provider)
    events.sort(key=lambda x: (x.time, x.location, x.title))
    return {"events": events}


if __name__ == "__main__":
    target_html = (
        Path("tests/data") / "view-source_https___www.eventbrite.ca_d_canada--calgary"
        "_all-events__page=1&start_date=2026-08-01&end_date=2026-08-01.html"
    )
    resolved_html_path = target_html.resolve()

    events_dict = parse_html_events_to_dict(
        resolved_html_path,
        event_date="2026-08-01",
    )
    logger.info("Extracted Events Dictionary:\n%s", events_dict)
