# src/eventus-publicus/services/enrich_events.py
# SPDX-FileCopyrightText: 2026 Sebastien Lenard <sebastien.lenard@gmail.com> and Contributors
# SPDX-License-Identifier: Apache-2.0
"""Service to enrich Event schemas with detailed information scraped from links."""

import asyncio
import logging

from bs4 import BeautifulSoup

from eventus_publicus.collectors.scraper import fetch_page_content
from eventus_publicus.readers.event_reader import parse_event_page_from_html
from eventus_publicus.schemas.event import Event

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("eventus_publicus.services.enrich_events")


async def enrich_event_details(
    events_data: dict[str, list[Event]],
) -> dict[str, list[Event]]:
    """Enrich each Event model instance in the collection with scraped details."""
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

        logger.info("Fetching details (%d/%d) for: %s", index, len(events), event.title)
        html_content = await fetch_page_content(event.link, timeout=25000)

        if not html_content:
            logger.warning("Failed to fetch HTML content for link: %s", event.link)
            continue

        soup = BeautifulSoup(html_content, "html.parser")
        details = parse_event_page_from_html(soup)

        # Update Event model attributes
        event.organizer = details.get("organizer")
        event.full_address = details.get("full_address")
        event.low_price = details.get("low_price")
        event.high_price = details.get("high_price")
        event.description = details.get("description", "")

        logger.info("Successfully enriched event: %s", event.title)

    logger.info("Enrichment process completed.")
    return events_data


async def main() -> None:
    """Execute the enrichment service using the requested sample event dataset."""
    sample_events_dict = {
        "events": [
            {
                "title": "Stand up Comedy at the Gallery!",
                "time": "Saturday at 7:00 PM",
                "location": "Calgary · Gallery Underground",
                "link": "https://www.eventbrite.com/e/stand-up-comedy-at-the-gallery-tickets-1994477731585?aff=ebdssbdestsearch",
            },
            {
                "title": "La Elegancia Latina: Summer Vibes",
                "time": "Saturday at 8:00 PM",
                "location": "Calgary · Heliopolis",
                "link": "https://www.eventbrite.ca/e/la-elegancia-latina-summer-vibes-tickets-1993233171071?aff=ebdssbdestsearch",
            },
        ],
    }

    logger.info("Running enrichment service main routine...")
    enriched_data = await enrich_event_details(sample_events_dict)

    # Output results for inspection
    for idx, ev in enumerate(enriched_data.get("events", []), start=1):
        logger.info("\n--- ENRICHED EVENT #%d ---", idx)
        for key, val in ev.items():
            # Truncate long description output for clear logging
            if key == "description" and val:
                logger.info("%s: [HTML Length: %d chars]", key, len(val))
            else:
                logger.info("%s: %s", key, val)


if __name__ == "__main__":
    asyncio.run(main())
