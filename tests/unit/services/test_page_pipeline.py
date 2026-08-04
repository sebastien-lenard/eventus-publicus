# tests/unit/services/test_page_pipeline.py
# SPDX-FileCopyrightText: 2026 Sebastien Lenard <sebastien.lenard@gmail.com> and Contributors
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for the page pipeline service module."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from eventus_publicus.schemas.event import Event
from eventus_publicus.services.page_pipeline import (
    PageOptions,
    main,
    scrape_and_enrich_events_for_date,
)


@pytest.mark.asyncio
async def test_scrape_and_enrich_empty_html() -> None:
    """Verify scrape_and_enrich_events_for_date returns empty list when empty HTML."""
    mock_provider = MagicMock()
    mock_provider.build_event_list_url.return_value = "https://example.com/list"

    with patch(
        "eventus_publicus.services.page_pipeline.fetch_page_content",
        new_callable=AsyncMock,
        return_value="",
    ):
        result = await scrape_and_enrich_events_for_date(
            1,
            "2026-08-01",
            provider=mock_provider,
        )
        assert result == {"events": []}


@pytest.mark.asyncio
async def test_scrape_and_enrich_file_not_found(tmp_path: Path) -> None:
    """Verify scrape_and_enrich_events_for_date returns empty list if no saved file."""
    mock_provider = MagicMock()
    mock_provider.build_event_list_url.return_value = "https://example.com/list"
    mock_provider.get_temporary_directory.return_value = tmp_path

    with (
        patch(
            "eventus_publicus.services.page_pipeline.fetch_page_content",
            new_callable=AsyncMock,
            return_value="<html></html>",
        ),
        patch.object(Path, "exists", return_value=False),
    ):
        result = await scrape_and_enrich_events_for_date(
            1,
            "2026-08-01",
            provider=mock_provider,
        )
        assert result == {"events": []}


@pytest.mark.asyncio
async def test_scrape_and_enrich_no_enrichment(tmp_path: Path) -> None:
    """Verify scrape_and_enrich_events_for_date returns non-enriched events."""
    mock_provider = MagicMock()
    mock_provider.build_event_list_url.return_value = "https://example.com/list"
    mock_provider.get_temporary_directory.return_value = tmp_path

    event = Event(
        date="2026-08-01",
        time="19:00",
        title="Event",
        link="https://example.com/1",
    )

    with (
        patch(
            "eventus_publicus.services.page_pipeline.fetch_page_content",
            new_callable=AsyncMock,
            return_value="<html></html>",
        ),
        patch(
            "eventus_publicus.services.page_pipeline.parse_html_events_to_dict",
            return_value={"events": [event]},
        ),
    ):
        result = await scrape_and_enrich_events_for_date(
            1,
            "2026-08-01",
            options=PageOptions(enrich=False),
            provider=mock_provider,
        )
        assert len(result["events"]) == 1
        assert result["events"][0].title == "Event"


@pytest.mark.asyncio
async def test_scrape_and_enrich_with_enrichment(tmp_path: Path) -> None:
    """Verify scrape_and_enrich_events_for_date calls enrich_event_details."""
    mock_provider = MagicMock()
    mock_provider.build_event_list_url.return_value = "https://example.com/list"
    mock_provider.get_temporary_directory.return_value = tmp_path

    event = Event(
        date="2026-08-01",
        time="19:00",
        title="Event",
        link="https://example.com/1",
    )

    with (
        patch(
            "eventus_publicus.services.page_pipeline.fetch_page_content",
            new_callable=AsyncMock,
            return_value="<html></html>",
        ),
        patch(
            "eventus_publicus.services.page_pipeline.parse_html_events_to_dict",
            return_value={"events": [event]},
        ),
        patch(
            "eventus_publicus.services.page_pipeline.enrich_event_details",
            new_callable=AsyncMock,
            return_value={"events": [event]},
        ) as mock_enrich,
    ):
        result = await scrape_and_enrich_events_for_date(
            1,
            "2026-08-01",
            options=PageOptions(enrich=True),
            provider=mock_provider,
        )
        mock_enrich.assert_awaited_once()
        assert len(result["events"]) == 1


@pytest.mark.asyncio
async def test_scrape_and_enrich_with_country(tmp_path: Path) -> None:
    """Verify scrape_and_enrich_events_for_date passes country option correctly."""
    mock_provider = MagicMock()
    mock_provider.build_event_list_url.return_value = "https://example.com/list"
    mock_provider.get_temporary_directory.return_value = tmp_path

    with (
        patch(
            "eventus_publicus.services.page_pipeline.fetch_page_content",
            new_callable=AsyncMock,
            return_value="<html></html>",
        ),
        patch(
            "eventus_publicus.services.page_pipeline.parse_html_events_to_dict",
            return_value={"events": []},
        ),
    ):
        await scrape_and_enrich_events_for_date(
            1,
            "2026-08-01",
            options=PageOptions(country="canada", city="calgary", enrich=False),
            provider=mock_provider,
        )
        mock_provider.build_event_list_url.assert_called_once_with(
            1,
            "2026-08-01",
            country="canada",
            city="calgary",
        )


@pytest.mark.asyncio
async def test_page_pipeline_main() -> None:
    """Verify main function in page_pipeline executes successfully."""
    event = Event(
        date="2027-12-01",
        time="19:00",
        title="Main Event",
        link="https://example.com/main",
    )
    with (
        patch(
            "eventus_publicus.services.page_pipeline.scrape_and_enrich_events_for_date",
            new_callable=AsyncMock,
            return_value={"events": [event]},
        ),
        patch(
            "eventus_publicus.services.page_pipeline.generate_markdown_report",
        ),
        patch.object(Path, "write_text"),
    ):
        await main()
