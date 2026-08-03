# src/eventus_publicus/services/enrich_events.py
# SPDX-FileCopyrightText: 2026 Sebastien Lenard <sebastien.lenard@gmail.com> and Contributors
# SPDX-License-Identifier: Apache-2.0
"""Service to enrich Event schemas with detailed information scraped from links."""

import asyncio
import logging
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from playwright.async_api import Error as PlaywrightError

from eventus_publicus.collectors.scraper import fetch_page_content
from eventus_publicus.providers.base import EventProvider
from eventus_publicus.providers.eventbrite import EventbriteProvider
from eventus_publicus.readers.event_reader import parse_event_page_from_html
from eventus_publicus.schemas.event import Event
from eventus_publicus.utils.config import AppConfig

logger = logging.getLogger(__name__)


async def enrich_event_details(
    events_data: dict[str, list[Event]],
    config: AppConfig | None = None,
    provider: EventProvider | None = None,
) -> dict[str, list[Event]]:
    """Enrich each Event model instance in the collection with scraped details."""
    active_provider = provider or EventbriteProvider()
    events = events_data.get("events", [])
    logger.info("Starting enrichment process for %d events...", len(events))

    for index, event in enumerate(events, start=1):
        if not event.link:
            logger.warning(
                "Event #%d ('%s') has no link. Skipping.",
                index,
                event.title,
            )
            continue

        parsed_url = urlparse(event.link)
        domain = parsed_url.netloc.lower()

        if domain and not active_provider.is_allowed_domain(domain):
            logger.warning(
                "Skipping enrichment for Event #%d ('%s'): Domain '%s' is not allowed.",
                index,
                event.title,
                domain,
            )
            event.description = (
                f"[Enrichment skipped: Domain '{domain}' is not allowed.] "
                f"{event.description}"
            ).strip()
            continue

        logger.info("Fetching details (%d/%d) for: %s", index, len(events), event.title)
        try:
            html_content = await fetch_page_content(
                event.link,
                timeout=25000,
                provider=active_provider,
                config=config,
            )
        except (PlaywrightError, OSError, TimeoutError, ValueError) as err:
            logger.warning(
                "Failed to fetch page content for Event #%d ('%s') due to %s: %s",
                index,
                event.title,
                err.__class__.__name__,
                err,
            )
            event.description = (
                f"[Enrichment failed: {err.__class__.__name__} - {err}] "
                f"{event.description}"
            ).strip()
            continue

        if not html_content:
            logger.warning("Failed to fetch HTML content for link: %s", event.link)
            event.description = (
                f"[Enrichment failed: Empty HTML response] {event.description}"
            ).strip()
            continue

        soup = BeautifulSoup(html_content, "html.parser")
        details = parse_event_page_from_html(soup, provider=active_provider)

        event.organizer = details.get("organizer")
        event.full_address = details.get("full_address")
        event.low_price = details.get("low_price")
        event.high_price = details.get("high_price")
        event.description = details.get("description", event.description)

        logger.info("Successfully enriched event: %s", event.title)

    logger.info("Enrichment process completed.")
    return events_data


async def main() -> None:
    """Execute the enrichment service using sample event dataset."""
    sample_events_dict: dict[str, list[Event]] = {
        "events": [
            Event(
                date="2026-08-01",
                title="Stand up Comedy at the Gallery!",
                time="Saturday at 7:00 PM",
                location="Calgary · Gallery Underground",
                link="https://www.eventbrite.com/e/stand-up-comedy-at-the-gallery-tickets-1994477731585?aff=ebdssbdestsearch",
            ),
        ],
    }

    logger.info("Running enrichment service main routine...")
    enriched_data = await enrich_event_details(sample_events_dict)

    for idx, ev in enumerate(enriched_data.get("events", []), start=1):
        logger.info("\n--- ENRICHED EVENT #%d ---", idx)
        for key, val in ev.model_dump().items():
            if key == "description" and val:
                logger.info("%s: [HTML Length: %d chars]", key, len(val))
            else:
                logger.info("%s: %s", key, val)


if __name__ == "__main__":
    asyncio.run(main())
