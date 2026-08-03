# tests/unit/services/test_enrich_events.py
# SPDX-FileCopyrightText: 2026 Sebastien Lenard <sebastien.lenard@gmail.com> and Contributors
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for the enrich events service module."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from playwright.async_api import Error as PlaywrightError

from eventus_publicus.schemas.event import Event
from eventus_publicus.services.enrich_events import enrich_event_details


@pytest.mark.asyncio
async def test_enrich_event_no_link() -> None:
    """Verify events without a link are skipped during enrichment."""
    event = Event(
        date="2026-08-01",
        time="19:00",
        title="No Link Event",
        link="",
    )
    result = await enrich_event_details({"events": [event]})
    assert result["events"][0].organizer is None


@pytest.mark.asyncio
async def test_enrich_event_disallowed_domain() -> None:
    """Verify events with disallowed domains skip fetching and update description."""
    event = Event(
        date="2026-08-01",
        time="19:00",
        title="External Event",
        link="https://evil.com/event",
        description="Original desc",
    )
    mock_provider = MagicMock()
    mock_provider.is_allowed_domain.return_value = False

    result = await enrich_event_details(
        {"events": [event]},
        provider=mock_provider,
    )
    assert "[Enrichment skipped" in result["events"][0].description
    assert "Original desc" in result["events"][0].description


@pytest.mark.asyncio
async def test_enrich_event_fetch_exception() -> None:
    """Verify exceptions during page fetching are handled and description updated."""
    event = Event(
        date="2026-08-01",
        time="19:00",
        title="Error Event",
        link="https://www.eventbrite.ca/e/error",
        description="Base desc",
    )
    mock_provider = MagicMock()
    mock_provider.is_allowed_domain.return_value = True

    with patch(
        "eventus_publicus.services.enrich_events.fetch_page_content",
        new_callable=AsyncMock,
        side_effect=PlaywrightError("Net error"),
    ):
        result = await enrich_event_details(
            {"events": [event]},
            provider=mock_provider,
        )
        assert "[Enrichment failed: Error" in result["events"][0].description
        assert "Base desc" in result["events"][0].description


@pytest.mark.asyncio
async def test_enrich_event_empty_html() -> None:
    """Verify empty HTML content is handled and description updated."""
    event = Event(
        date="2026-08-01",
        time="19:00",
        title="Empty HTML Event",
        link="https://www.eventbrite.ca/e/empty",
        description="Base desc",
    )
    mock_provider = MagicMock()
    mock_provider.is_allowed_domain.return_value = True

    with patch(
        "eventus_publicus.services.enrich_events.fetch_page_content",
        new_callable=AsyncMock,
        return_value="",
    ):
        result = await enrich_event_details(
            {"events": [event]},
            provider=mock_provider,
        )
        assert (
            "[Enrichment failed: Empty HTML response]"
            in result["events"][0].description
        )
        assert "Base desc" in result["events"][0].description


@pytest.mark.asyncio
async def test_enrich_event_success() -> None:
    """Verify successful event enrichment updates organizer, address, prices, and description."""
    event = Event(
        date="2026-08-01",
        time="19:00",
        title="Valid Event",
        link="https://www.eventbrite.ca/e/valid",
        description="Old description",
    )
    mock_provider = MagicMock()
    mock_provider.is_allowed_domain.return_value = True

    parsed_details = {
        "organizer": "Test Organizer",
        "full_address": "123 Test St",
        "low_price": 10.0,
        "high_price": 25.0,
        "description": "<p>Enriched description</p>",
    }

    with (
        patch(
            "eventus_publicus.services.enrich_events.fetch_page_content",
            new_callable=AsyncMock,
            return_value="<html></html>",
        ),
        patch(
            "eventus_publicus.services.enrich_events.parse_event_page_from_html",
            return_value=parsed_details,
        ),
    ):
        result = await enrich_event_details(
            {"events": [event]},
            provider=mock_provider,
        )
        enriched = result["events"][0]
        assert enriched.organizer == "Test Organizer"
        assert enriched.full_address == "123 Test St"
        assert enriched.low_price == 10.0
        assert enriched.high_price == 25.0
        assert enriched.description == "<p>Enriched description</p>"
