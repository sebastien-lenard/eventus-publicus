# tests/unit/services/test_date_range_pipeline.py
# SPDX-FileCopyrightText: 2026 Sebastien Lenard <sebastien.lenard@gmail.com> and Contributors
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for the date range pipeline service module."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from eventus_publicus.schemas.event import Event
from eventus_publicus.services.date_range_pipeline import (
    PipelineOptions,
    ScrapeContext,
    _daterange,
    _load_cached_events,
    _scrape_single_date,
    scrape_events_for_date_range,
)


def test_daterange() -> None:
    """Verify _daterange generates correct sequence of date strings inclusive."""
    dates = _daterange("2026-08-01", "2026-08-03")
    assert dates == ["2026-08-01", "2026-08-02", "2026-08-03"]


@pytest.mark.asyncio
async def test_load_cached_events_success(tmp_path: Path) -> None:
    """Verify _load_cached_events successfully loads and validates cached events."""
    mock_provider = MagicMock()
    cache_file = tmp_path / "cache.json"
    mock_provider.get_cache_file_path.return_value = cache_file

    event_data = {
        "events": [
            {
                "date": "2026-08-01",
                "time": "18:00",
                "title": "Cached Event",
                "link": "https://example.com/cached",
            },
        ],
    }
    cache_file.write_text(json.dumps(event_data), encoding="utf-8")

    events = await _load_cached_events("2026-08-01", provider=mock_provider)
    assert events is not None
    assert len(events) == 1
    assert events[0].title == "Cached Event"


@pytest.mark.asyncio
async def test_load_cached_events_invalid_json(tmp_path: Path) -> None:
    """Verify _load_cached_events handles invalid cache JSON and returns None."""
    mock_provider = MagicMock()
    cache_file = tmp_path / "cache.json"
    mock_provider.get_cache_file_path.return_value = cache_file
    cache_file.write_text("INVALID JSON", encoding="utf-8")

    events = await _load_cached_events("2026-08-01", provider=mock_provider)
    assert events is None


@pytest.mark.asyncio
async def test_load_cached_events_missing(tmp_path: Path) -> None:
    """Verify _load_cached_events returns None when cache file does not exist."""
    mock_provider = MagicMock()
    cache_file = tmp_path / "non_existent.json"
    mock_provider.get_cache_file_path.return_value = cache_file

    events = await _load_cached_events("2026-08-01", provider=mock_provider)
    assert events is None


@pytest.mark.asyncio
async def test_scrape_single_date() -> None:
    """Verify _scrape_single_date iterates pages, filters, and enriches events."""
    mock_filter_service = MagicMock()
    event = Event(
        date="2026-08-01",
        time="19:00",
        title="Event 1",
        link="https://example.com/1",
    )
    mock_filter_service.filter_events.return_value = [event]

    progress_calls = []
    options = PipelineOptions(
        enrich=True,
        on_progress=lambda d, p, tp, td, di: progress_calls.append(
            (d, p, tp, td, di),
        ),
    )
    ctx = ScrapeContext(
        date_str="2026-08-01",
        tmp_dir=Path("dummy_dir"),
        filter_service=mock_filter_service,
        options=options,
        total_dates=1,
        date_idx=1,
    )

    with (
        patch(
            "eventus_publicus.services.date_range_pipeline.scrape_and_enrich_events_for_date",
            new_callable=AsyncMock,
            return_value={"events": [event]},
        ),
        patch(
            "eventus_publicus.services.date_range_pipeline.check_page_status",
            return_value=(False, 1, 1),
        ),
        patch(
            "eventus_publicus.services.date_range_pipeline.enrich_event_details",
            new_callable=AsyncMock,
            return_value={"events": [event]},
        ),
    ):
        events = await _scrape_single_date(ctx)
        assert len(events) == 1
        assert events[0].title == "Event 1"
        assert len(progress_calls) > 0


@pytest.mark.asyncio
async def test_scrape_single_date_multi_page_and_no_results(tmp_path: Path) -> None:
    """Verify _scrape_single_date handles multi-page pagination and no-results check."""
    mock_filter_service = MagicMock()
    event1 = Event(
        date="2026-08-01",
        time="19:00",
        title="Event Page 1",
        link="https://example.com/1",
    )
    mock_filter_service.filter_events.side_effect = lambda evs: evs

    options = PipelineOptions(enrich=False)
    ctx = ScrapeContext(
        date_str="2026-08-01",
        tmp_dir=tmp_path,
        filter_service=mock_filter_service,
        options=options,
        total_dates=1,
        date_idx=1,
    )

    # Create dummy saved file for page 1
    saved_file_p1 = tmp_path / "all-events-2026-08-01-page1.html"
    saved_file_p1.write_text("content", encoding="utf-8")
    saved_file_p2 = tmp_path / "all-events-2026-08-01-page2.html"
    saved_file_p2.write_text("content", encoding="utf-8")

    def side_effect_check_status(path: Path) -> tuple[bool, int, int]:
        if "page1" in str(path):
            return (False, 1, 2)  # page 1 of 2 (triggers page_number += 1)
        return (True, 2, 2)  # page 2 has no results (triggers break)

    with (
        patch(
            "eventus_publicus.services.date_range_pipeline.scrape_and_enrich_events_for_date",
            new_callable=AsyncMock,
            side_effect=[
                {"events": [event1]},
                {"events": []},
            ],
        ),
        patch(
            "eventus_publicus.services.date_range_pipeline.check_page_status",
            side_effect=side_effect_check_status,
        ),
    ):
        events = await _scrape_single_date(ctx)
        assert len(events) == 1
        assert events[0].title == "Event Page 1"


@pytest.mark.asyncio
async def test_scrape_single_date_empty_events() -> None:
    """Verify _scrape_single_date breaks early when page returns no events."""
    mock_filter_service = MagicMock()
    options = PipelineOptions(enrich=False)
    ctx = ScrapeContext(
        date_str="2026-08-01",
        tmp_dir=Path("dummy_dir"),
        filter_service=mock_filter_service,
        options=options,
        total_dates=1,
        date_idx=1,
    )

    with patch(
        "eventus_publicus.services.date_range_pipeline.scrape_and_enrich_events_for_date",
        new_callable=AsyncMock,
        return_value={"events": []},
    ):
        events = await _scrape_single_date(ctx)
        assert events == []


@pytest.mark.asyncio
async def test_scrape_events_for_date_range_pipeline(tmp_path: Path) -> None:
    """Verify scrape_events_for_date_range orchestrates multi-date scraping and deduplication."""
    mock_provider = MagicMock()
    mock_provider.get_temporary_directory.return_value = tmp_path
    mock_provider.get_cache_file_path.return_value = tmp_path / "cache.json"

    event1 = Event(
        date="2026-08-01",
        time="19:00",
        title="Event 1",
        link="https://example.com/1",
    )
    event2 = Event(
        date="2026-08-01",
        time="19:00",
        title="Event 1",
        link="https://example.com/1",
    )  # duplicate identity

    progress_calls = []
    options = PipelineOptions(
        enrich=False,
        use_cache=False,
        on_progress=lambda d, p, tp, td, di: progress_calls.append(
            (d, p, tp, td, di),
        ),
    )

    with patch(
        "eventus_publicus.services.date_range_pipeline._scrape_single_date",
        new_callable=AsyncMock,
        return_value=[event1, event2],
    ):
        result = await scrape_events_for_date_range(
            "2026-08-01",
            "2026-08-01",
            options=options,
            provider=mock_provider,
        )
        assert "events" in result
        # Deduplication should leave only 1 event
        assert len(result["events"]) == 1


@pytest.mark.asyncio
async def test_scrape_events_for_date_range_cache_hit(tmp_path: Path) -> None:
    """Verify scrape_events_for_date_range uses cache when use_cache=True and cache exists."""
    mock_provider = MagicMock()
    mock_provider.get_temporary_directory.return_value = tmp_path
    cache_file = tmp_path / "cache.json"
    mock_provider.get_cache_file_path.return_value = cache_file

    event = Event(
        date="2026-08-01",
        time="19:00",
        title="Cached Event",
        link="https://example.com/cached",
    )
    cache_file.write_text(
        json.dumps({"events": [event.model_dump()]}),
        encoding="utf-8",
    )

    options = PipelineOptions(use_cache=True)
    result = await scrape_events_for_date_range(
        "2026-08-01",
        "2026-08-01",
        options=options,
        provider=mock_provider,
    )
    assert len(result["events"]) == 1
    assert result["events"][0].title == "Cached Event"


@pytest.mark.asyncio
async def test_scrape_events_for_date_range_cache_write_error(tmp_path: Path) -> None:
    """Verify cache write OSError is handled gracefully during date range scraping."""
    mock_provider = MagicMock()
    mock_provider.get_temporary_directory.return_value = tmp_path
    cache_file = tmp_path / "cache.json"
    mock_provider.get_cache_file_path.return_value = cache_file

    event = Event(
        date="2026-08-01",
        time="19:00",
        title="Event",
        link="https://example.com/1",
    )
    options = PipelineOptions(use_cache=False)

    with (
        patch(
            "eventus_publicus.services.date_range_pipeline._scrape_single_date",
            new_callable=AsyncMock,
            return_value=[event],
        ),
        patch.object(Path, "write_text", side_effect=OSError("Disk full")),
    ):
        result = await scrape_events_for_date_range(
            "2026-08-01",
            "2026-08-01",
            options=options,
            provider=mock_provider,
        )
        assert len(result["events"]) == 1
