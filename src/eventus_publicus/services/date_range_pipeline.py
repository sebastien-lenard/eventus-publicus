# src/eventus-publicus/services/date_range_pipeline.py
# SPDX-FileCopyrightText: 2026 Sebastien Lenard <sebastien.lenard@gmail.com> and Contributors
# SPDX-License-Identifier: Apache-2.0
"""Multi-date pipeline to scrape pagination series, filter, enrich, save reports."""

import asyncio
import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from eventus_publicus.providers.eventbrite import (
    get_cache_file_path,
    get_temporary_directory,
)
from eventus_publicus.readers.list_reader import check_page_status
from eventus_publicus.schemas.event import Event
from eventus_publicus.services.enrich_events import enrich_event_details
from eventus_publicus.services.event_pipeline import (
    scrape_and_enrich_events_for_date,
)
from eventus_publicus.services.filter_service import EventFilterService
from eventus_publicus.utils.config import AppConfig

logger = logging.getLogger(__name__)


@dataclass
class PipelineOptions:
    """Options controlling scraping pipeline execution behavior."""

    enrich: bool = True
    use_cache: bool = True
    on_progress: Callable[[str, int, int, int, int], None] | None = None


@dataclass
class ScrapeContext:
    """Context object to bundle arguments and avoid too many function parameters."""

    date_str: str
    tmp_dir: Path
    filter_service: EventFilterService
    options: PipelineOptions
    total_dates: int
    date_idx: int
    config: AppConfig | None = None


def _daterange(start_date: str, end_date: str) -> list[str]:
    """Generate list of date strings (YYYY-MM-DD) from start to end inclusive."""
    start = datetime.strptime(start_date, "%Y-%m-%d").replace(
        tzinfo=UTC,
    )
    end = datetime.strptime(end_date, "%Y-%m-%d").replace(
        tzinfo=UTC,
    )
    delta = timedelta(days=1)

    dates = []
    curr = start
    while curr <= end:
        dates.append(curr.strftime("%Y-%m-%d"))
        curr += delta
    return dates


async def _load_cached_events(
    date_str: str,
    location: str = "calgary",
    config: AppConfig | None = None,
) -> list[Event] | None:
    """Attempt to load cached events for a given date and location."""
    date_json_path = get_cache_file_path(date_str, location, config=config)
    if date_json_path.exists():
        logger.info(
            "Loading cached events for date %s (%s) from %s",
            date_str,
            location,
            date_json_path,
        )
        try:
            cached_data = json.loads(
                date_json_path.read_text(encoding="utf-8"),
            )
            return [
                Event.model_validate(item) for item in cached_data.get("events", [])
            ]
        except Exception:
            logger.exception(
                "Failed to load cache for %s. Falling back to scraper.",
                date_str,
            )
    return None


async def _scrape_single_date(ctx: ScrapeContext) -> list[Event]:
    """Scrape, filter, and optionally enrich all pages for a single date."""
    date_events: list[Event] = []
    page_number = 1
    total_pages = 1

    while page_number <= total_pages:
        if ctx.options.on_progress:
            ctx.options.on_progress(
                ctx.date_str,
                page_number,
                total_pages,
                ctx.total_dates,
                ctx.date_idx,
            )

        logger.info(
            "Fetching page %d for date %s (Est. total: %d)",
            page_number,
            ctx.date_str,
            total_pages,
        )

        result_dict = await scrape_and_enrich_events_for_date(
            page_number,
            ctx.date_str,
            enrich=False,
            config=ctx.config,
        )

        saved_file_path = (
            ctx.tmp_dir / f"all-events-{ctx.date_str}-page{page_number}.html"
        )

        if saved_file_path.exists():
            has_no_results, _cur_p, tot_p = check_page_status(saved_file_path)
            total_pages = max(total_pages, tot_p)

            if has_no_results:
                logger.info(
                    "Encountered 'Nothing matched your search' on page %d.",
                    page_number,
                )
                break

        page_events = result_dict.get("events", [])

        if not page_events:
            logger.info("No events on page %d for date %s.", page_number, ctx.date_str)
            break

        filtered_page_events = ctx.filter_service.filter_events(page_events)

        if filtered_page_events and ctx.options.enrich:
            logger.info(
                "Enriching %d filtered events for date %s...",
                len(filtered_page_events),
                ctx.date_str,
            )
            enriched_dict = await enrich_event_details(
                {"events": filtered_page_events},
                config=ctx.config,
            )
            filtered_page_events = enriched_dict.get("events", [])

        date_events.extend(filtered_page_events)

        if page_number >= total_pages:
            logger.info(
                "Reached final page (%d/%d) for date %s.",
                page_number,
                total_pages,
                ctx.date_str,
            )
            break

        page_number += 1

    date_events.sort(key=lambda x: (x.time, x.location, x.title))
    return date_events


async def scrape_events_for_date_range(
    start_date: str,
    end_date: str,
    *,
    options: PipelineOptions | None = None,
    config: AppConfig | None = None,
) -> dict[str, list[Event]]:
    """Scrape multiple pages per date, or load from cache if present."""
    pipeline_options = options or PipelineOptions()
    all_accumulated_events: list[Event] = []
    dates = _daterange(start_date, end_date)

    tmp_dir = get_temporary_directory(config=config)
    filter_service = EventFilterService(config=config)
    total_dates = len(dates)
    location = "calgary"

    for date_idx, date_str in enumerate(dates, start=1):
        if pipeline_options.on_progress:
            pipeline_options.on_progress(date_str, 1, 1, total_dates, date_idx)

        if pipeline_options.use_cache:
            cached = await _load_cached_events(date_str, location, config=config)
            if cached is not None:
                all_accumulated_events.extend(cached)
                continue

        logger.info("=== Starting processing for date: %s ===", date_str)
        ctx = ScrapeContext(
            date_str=date_str,
            tmp_dir=tmp_dir,
            filter_service=filter_service,
            options=pipeline_options,
            total_dates=total_dates,
            date_idx=date_idx,
            config=config,
        )
        date_events = await _scrape_single_date(ctx)

        logger.info("Completed %s: Found %d total events.", date_str, len(date_events))
        all_accumulated_events.extend(date_events)

        date_json_path = get_cache_file_path(date_str, location, config=config)
        try:
            serialized = {"events": [ev.model_dump() for ev in date_events]}
            date_json_path.write_text(
                json.dumps(serialized, indent=4, ensure_ascii=False),
                encoding="utf-8",
            )
            logger.info("Saved accumulated events for %s to cache JSON", date_str)
        except OSError:
            logger.exception("Failed to write cache JSON for date %s", date_str)

    seen_identities: set[str] = set()
    unique_events: list[Event] = []
    for ev in all_accumulated_events:
        identity = ev.unique_identity
        if identity not in seen_identities:
            seen_identities.add(identity)
            unique_events.append(ev)

    unique_events.sort(
        key=lambda x: (x.date, x.time, x.location, x.title),
    )
    return {"events": unique_events}


async def main() -> None:
    """Execute date-range service with cache enabled."""
    start_date = "2026-08-03"
    end_date = "2026-08-09"

    logger.info(
        "Starting multi-date pipeline execution from %s to %s",
        start_date,
        end_date,
    )

    full_result_dict = await scrape_events_for_date_range(
        start_date,
        end_date,
        options=PipelineOptions(enrich=False, use_cache=True),
    )
    events = full_result_dict.get("events", [])

    if not events:
        logger.warning("No events were found across the specified date range.")
        return

    logger.info("Total accumulated events processed: %d", len(events))


if __name__ == "__main__":
    asyncio.run(main())
