# src/eventus-publicus/services/event_pipeline.py
# SPDX-FileCopyrightText: 2026 Sebastien Lenard <sebastien.lenard@gmail.com> and Contributors
# SPDX-License-Identifier: Apache-2.0
"""Pipeline service to construct search URLs, scrape lists, and enrich event data."""

import asyncio
import json
import logging

from eventus_publicus.collectors.scraper import fetch_page_content
from eventus_publicus.providers.base import EventProvider
from eventus_publicus.providers.eventbrite import EventbriteProvider
from eventus_publicus.readers.list_reader import parse_html_events_to_dict
from eventus_publicus.schemas.event import Event
from eventus_publicus.services.enrich_events import enrich_event_details
from eventus_publicus.utils.config import AppConfig
from eventus_publicus.writers.markdown_writer import generate_markdown_report

logger = logging.getLogger(__name__)


async def scrape_and_enrich_events_for_date(
    page_number: int,
    date: str,
    *,
    enrich: bool = True,
    provider: EventProvider | None = None,
    config: AppConfig | None = None,
) -> dict[str, list[Event]]:
    """Construct search URL, scrape list, parse events, and optionally enrich."""
    active_provider = provider or EventbriteProvider()
    target_url = active_provider.build_event_list_url(page_number, date)
    logger.info("Generated target event list URL: %s", target_url)

    html_content = await fetch_page_content(
        target_url,
        timeout=25000,
        provider=active_provider,
        config=config,
    )
    if not html_content:
        logger.warning(
            "Failed to fetch HTML content for listing URL: %s",
            target_url,
        )
        return {"events": []}

    clean_url = target_url.split("?")[0].split("#")[0]
    path_segments = [seg for seg in clean_url.split("/") if seg]
    last_segment = path_segments[-1] if path_segments else "index"

    saved_file_path = (
        active_provider.get_temporary_directory(config=config)
        / f"{last_segment}-{date}-page{page_number}.html"
    )

    saved_file_path.parent.mkdir(parents=True, exist_ok=True)
    saved_file_path.write_text(html_content, encoding="utf-8")

    if not saved_file_path.exists():
        logger.error("Expected saved HTML file not found at: %s", saved_file_path)
        return {"events": []}

    events_dict = parse_html_events_to_dict(
        saved_file_path,
        event_date=date,
        provider=active_provider,
    )
    event_count = len(events_dict.get("events", []))
    logger.info(
        "Successfully extracted %d events from the listing page for date %s.",
        event_count,
        date,
    )

    if not enrich:
        logger.info("Enrichment is deactivated by flag. Returning base event list.")
        return events_dict

    return await enrich_event_details(events_dict, config=config)


async def main() -> None:
    """Execute pipeline for page 1, date 2027-12-01, saving report & printing events."""
    page_num = 1
    target_date = "2027-12-01"

    logger.info(
        "Starting pipeline execution for Page: %d, Date: %s",
        page_num,
        target_date,
    )

    result_dict = await scrape_and_enrich_events_for_date(page_num, target_date)
    events: list[Event] = result_dict.get("events", [])

    if not events:
        logger.warning(
            "No events were found or enriched for the given parameters.",
        )
        return

    generate_markdown_report(events_data=result_dict)

    json_file_path = (
        EventbriteProvider().get_temporary_directory()
        / f"events-calgary-{target_date}-page{page_num}.json"
    )

    try:
        serialized_data = {
            "events": [ev.model_dump() for ev in events],
        }
        json_content = json.dumps(serialized_data, indent=4, ensure_ascii=False)
        json_file_path.write_text(json_content, encoding="utf-8")
    except (TypeError, ValueError):
        logger.exception(
            "Failed to serialize events dictionary to JSON",
        )
        raise
    except OSError:
        logger.exception(
            "Disk I/O error while writing JSON file to %s",
            json_file_path,
        )
        raise

    logger.debug(
        "Saved enriched events JSON dictionary to: %s",
        json_file_path.resolve(),
    )

    logger.info("\n================ PIPELINE SUMMARY ================")
    logger.info("Total events processed & enriched: %d\n", len(events))

    logger.info("--- FIRST EVENT ---")
    for key, value in events[0].model_dump().items():
        if key == "description" and value:
            logger.info("  %s: [HTML Content Length: %d chars]", key, len(value))
        else:
            logger.info("  %s: %s", key, value)

    if len(events) > 1:
        logger.info("\n--- LAST EVENT ---")
        for key, value in events[-1].model_dump().items():
            if key == "description" and value:
                logger.info(
                    "  %s: [HTML Content Length: %d chars]",
                    key,
                    len(value),
                )
            else:
                logger.info("  %s: %s", key, value)


if __name__ == "__main__":
    asyncio.run(main())
