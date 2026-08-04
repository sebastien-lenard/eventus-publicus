# tests/integ/test_eventbrite_live.py
# SPDX-FileCopyrightText: 2026 Sebastien Lenard <sebastien.lenard@gmail.com> and Contributors
# SPDX-License-Identifier: Apache-2.0
"""Live integration tests for EventbriteProvider against real eventbrite.ca pages."""

from datetime import UTC, datetime, timedelta

import pytest
from bs4 import BeautifulSoup, Tag

from eventus_publicus.fetchers.scraper import fetch_page_content
from eventus_publicus.providers.eventbrite import EventbriteProvider

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_eventbrite_listing_page_live() -> None:
    """Verify tomorrow's Calgary event listing page loads and contains selectors."""
    provider = EventbriteProvider()
    tomorrow = (datetime.now(tz=UTC) + timedelta(days=1)).strftime("%Y-%m-%d")
    url = provider.build_event_list_url(page_number=1, date=tomorrow)

    html_content = await fetch_page_content(url, timeout=30000, provider=provider)
    assert html_content, "Listing page returned empty HTML content."

    soup = BeautifulSoup(html_content, "html.parser")
    container_selector, card_selector = provider.get_event_list_card_selectors()

    container = soup.select_one(container_selector)
    assert container is not None, (
        f"Event list container selector '{container_selector}' not found on live page."
    )

    cards = container.select(card_selector)
    assert len(cards) > 0, (
        f"Expected at least one event card using selector '{card_selector}', found 0."
    )


@pytest.mark.asyncio
async def test_eventbrite_zero_results_page_live() -> None:
    """Verify historical date (2022-11-01) triggers zero search results status."""
    provider = EventbriteProvider()
    historical_date = "2022-11-01"
    url = provider.build_event_list_url(page_number=1, date=historical_date)

    html_content = await fetch_page_content(url, timeout=30000, provider=provider)
    assert html_content, "Zero-results page returned empty HTML content."

    soup = BeautifulSoup(html_content, "html.parser")
    text_content = soup.get_text()

    has_no_results = provider.check_search_status(text_content)
    assert has_no_results is True, (
        "Expected zero-results search status message, but none was detected."
    )


@pytest.mark.asyncio
async def test_eventbrite_detail_page_live() -> None:
    """Verify an individual event detail page loads and contains selectors."""
    provider = EventbriteProvider()
    tomorrow = (datetime.now(tz=UTC) + timedelta(days=1)).strftime("%Y-%m-%d")
    listing_url = provider.build_event_list_url(page_number=1, date=tomorrow)

    listing_html = await fetch_page_content(
        listing_url,
        timeout=30000,
        provider=provider,
    )
    assert listing_html, "Listing page returned empty HTML for detail test setup."

    soup = BeautifulSoup(listing_html, "html.parser")
    container_selector, card_selector = provider.get_event_list_card_selectors()
    container = soup.select_one(container_selector)

    if not container:
        pytest.skip("No event container found on listing page; skipping detail test.")

    cards = container.select(card_selector)
    if not cards:
        pytest.skip("No event cards found on listing page; skipping detail test.")

    first_card = cards[0]
    first_a = first_card.find("a")

    link = ""
    if isinstance(first_a, Tag):
        href = first_a.get("href", "")
        link = (href[0] if href else "") if isinstance(href, list) else str(href)

    if not link:
        pytest.skip(
            "Could not extract a valid event link from the first card; skipping.",
        )

    if link.startswith("/"):
        link = f"https://www.eventbrite.ca{link}"

    detail_html = await fetch_page_content(link, timeout=30000, provider=provider)
    assert detail_html, f"Detail page at {link} returned empty HTML."

    detail_soup = BeautifulSoup(detail_html, "html.parser")

    json_ld_scripts = detail_soup.find_all("script", type="application/ld+json")
    overview_selector = provider.get_description_overview_selector()
    overview_div = detail_soup.select_one(overview_selector)

    assert json_ld_scripts or overview_div, (
        "Expected either JSON-LD schema or description overview selector "
        "to be present on the event detail page."
    )
