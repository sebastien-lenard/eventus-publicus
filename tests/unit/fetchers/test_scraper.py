# tests/unit/fetchers/test_scraper.py
# SPDX-FileCopyrightText: 2026 Sebastien Lenard <sebastien.lenard@gmail.com> and Contributors
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for the scraper fetcher module."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from playwright.async_api import Error as PlaywrightError

from eventus_publicus.fetchers.scraper import (
    DomainRateLimiter,
    _save_html_to_temp,
    _setup_network_interceptors,
    _setup_page_event_listeners,
    async_retry,
    fetch_page_content,
)
from eventus_publicus.fetchers.scraper import (
    test_playwright_basic as run_playwright_basic,
)
from eventus_publicus.providers.eventbrite import EventbriteProvider


@pytest.mark.asyncio
async def test_async_retry_success_on_first_try() -> None:
    """Verify that a function succeeding immediately executes without retries."""
    mock_func = AsyncMock(return_value="success")
    decorated = async_retry(retries=3, base_delay=0.01)(mock_func)

    result = await decorated()
    assert result == "success"
    assert mock_func.await_count == 1


@pytest.mark.asyncio
async def test_async_retry_success_after_failures() -> None:
    """Verify that function retries on specified exceptions and eventually succeeds."""
    mock_func = AsyncMock(
        side_effect=[OSError("Network glitch"), OSError("Timeout"), "recovered"],
    )
    # Patch asyncio.sleep to speed up test execution
    with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        decorated = async_retry(
            retries=3,
            base_delay=0.01,
            exceptions=(OSError,),
        )(mock_func)
        result = await decorated()

    assert result == "recovered"
    assert mock_func.await_count == 3
    assert mock_sleep.await_count == 2


@pytest.mark.asyncio
async def test_async_retry_exhausted_raises_exception() -> None:
    """Verify that exceeding max retries raises the original exception."""
    mock_func = AsyncMock(side_effect=OSError("Permanent failure"))
    decorated = async_retry(
        retries=2,
        base_delay=0.01,
        exceptions=(OSError,),
    )(mock_func)

    with (
        patch("asyncio.sleep", new_callable=AsyncMock),
        pytest.raises(OSError, match="Permanent failure"),
    ):
        await decorated()

    assert mock_func.await_count == 3  # Initial attempt + 2 retries


@pytest.mark.asyncio
async def test_async_retry_unhandled_exception_raises_immediately() -> None:
    """Verify that exceptions not in the tuple raise immediately without retrying."""
    mock_func = AsyncMock(side_effect=ValueError("Unexpected error"))
    decorated = async_retry(
        retries=3,
        base_delay=0.01,
        exceptions=(OSError,),
    )(mock_func)

    with (
        patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
        pytest.raises(ValueError, match="Unexpected error"),
    ):
        await decorated()

    assert mock_func.await_count == 1
    mock_sleep.assert_not_awaited()


@pytest.mark.asyncio
async def test_domain_rate_limiter_behavior() -> None:
    """Verify domain rate limiter waits when called rapidly for the same domain."""
    limiter = DomainRateLimiter(min_interval=0.1)

    url1 = "https://www.eventbrite.ca/e/some-event-123?foo=bar"
    url2 = "https://www.eventbrite.ca/e/other-event-456"
    url_other_domain = "https://example.com/page"
    url_empty = ""

    with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        # First request to domain -> no wait
        await limiter.wait_if_needed(url1)
        mock_sleep.assert_not_awaited()

        # Immediate second request to same domain -> should sleep
        await limiter.wait_if_needed(url2)
        assert mock_sleep.await_count == 1

        # Request to a different domain -> should not sleep relative to eventbrite
        await limiter.wait_if_needed(url_other_domain)

        # Request with empty URL -> returns immediately
        await limiter.wait_if_needed(url_empty)


def test_save_html_to_temp(tmp_path: Path) -> None:
    """Verify HTML saving utility correctly writes file into provider temp directory."""
    provider = EventbriteProvider()
    test_url = "https://www.eventbrite.ca/e/cool-event-tickets-99999?aff=test"
    test_content = "<html><body><h1>Test Event</h1></body></html>"

    mock_config = MagicMock()

    with patch.object(
        provider,
        "get_temporary_directory",
        return_value=tmp_path,
    ) as mock_get_tmp:
        _save_html_to_temp(test_url, test_content, provider, config=mock_config)

        mock_get_tmp.assert_called_once_with(config=mock_config)
        expected_file = tmp_path / "cool-event-tickets-99999.html"
        assert expected_file.exists()
        assert expected_file.read_text(encoding="utf-8") == test_content


def test_save_html_to_temp_empty_content(tmp_path: Path) -> None:
    """Verify empty content is ignored and no file is written."""
    provider = EventbriteProvider()
    _save_html_to_temp("https://example.com", "", provider)
    assert not list(tmp_path.iterdir())


@pytest.mark.asyncio
async def test_fetch_page_content_with_context() -> None:
    """Verify fetch_page_content utilizing an existing mock BrowserContext."""
    mock_page = MagicMock()
    mock_page.on = MagicMock()
    mock_page.route = AsyncMock()
    mock_page.add_init_script = AsyncMock()
    mock_page.unroute_all = AsyncMock()
    mock_page.close = AsyncMock()
    mock_page.content = AsyncMock(return_value="<html>Mocked Page</html>")
    mock_page.goto = AsyncMock(
        return_value=MagicMock(status=200),
    )

    mock_context = AsyncMock()
    mock_context.new_page = AsyncMock(return_value=mock_page)

    mock_provider = MagicMock()
    mock_provider.is_allowed_domain.return_value = True
    mock_provider.smart_wait_for_page = AsyncMock()

    result = await fetch_page_content(
        "https://www.eventbrite.ca/e/test-event",
        timeout=1000,
        context=mock_context,
        provider=mock_provider,
    )

    assert result == "<html>Mocked Page</html>"
    mock_context.new_page.assert_awaited_once()
    mock_page.goto.assert_awaited_once()
    mock_page.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_fetch_page_content_launch_browser() -> None:
    """Verify fetch_page_content launching new browser when context is None."""
    mock_page = MagicMock()
    mock_page.on = MagicMock()
    mock_page.route = AsyncMock()
    mock_page.add_init_script = AsyncMock()
    mock_page.unroute_all = AsyncMock()
    mock_page.close = AsyncMock()
    mock_page.content = AsyncMock(
        return_value="<html>Fresh Browser Page</html>",
    )
    mock_page.goto = AsyncMock(
        return_value=MagicMock(status=200),
    )

    mock_context = AsyncMock()
    mock_context.new_page = AsyncMock(return_value=mock_page)

    mock_browser = AsyncMock()
    mock_browser.new_context = AsyncMock(return_value=mock_context)
    mock_browser.close = AsyncMock()

    mock_playwright = AsyncMock()
    mock_playwright.chromium.launch = AsyncMock(return_value=mock_browser)

    mock_provider = MagicMock()
    mock_provider.is_allowed_domain.return_value = True
    mock_provider.smart_wait_for_page = AsyncMock()

    with patch(
        "eventus_publicus.fetchers.scraper.async_playwright",
    ) as mock_async_pw:
        mock_async_pw.return_value.__aenter__.return_value = mock_playwright

        result = await fetch_page_content(
            "https://www.eventbrite.ca/e/test-event",
            timeout=1000,
            provider=mock_provider,
        )

    assert result == "<html>Fresh Browser Page</html>"
    mock_playwright.chromium.launch.assert_awaited_once()
    mock_browser.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_test_playwright_basic_success() -> None:
    """Verify test_playwright_basic passes when expected text is present."""
    with patch(
        "eventus_publicus.fetchers.scraper.fetch_page_content",
        new_callable=AsyncMock,
        return_value="<html><body>Herman Melville was an author.</body></html>",
    ):
        success = await run_playwright_basic()
        assert success is True


@pytest.mark.asyncio
async def test_test_playwright_basic_failure() -> None:
    """Verify test_playwright_basic fails when content is empty."""
    with patch(
        "eventus_publicus.fetchers.scraper.fetch_page_content",
        new_callable=AsyncMock,
        return_value="",
    ):
        success = await run_playwright_basic()
        assert success is False


@pytest.mark.asyncio
async def test_test_playwright_basic_failure_wrong_content() -> None:
    """Verify test_playwright_basic fails when expected substring is absent."""
    with patch(
        "eventus_publicus.fetchers.scraper.fetch_page_content",
        new_callable=AsyncMock,
        return_value="<html><body>Some other content.</body></html>",
    ):
        success = await run_playwright_basic()
        assert success is False


@pytest.mark.asyncio
async def test_network_interceptors_and_listeners() -> None:
    """Test network interceptor route handler and page event listeners."""
    mock_page = MagicMock()
    listeners = {}
    mock_page.on = lambda event, cb: listeners.update({event: cb})

    # Trigger listener setup
    _setup_page_event_listeners(mock_page)

    # Test requestfailed listener branches
    req_failed_handler = listeners.get("requestfailed")
    if req_failed_handler:
        # Intentionally blocked request (should log debug and return)
        blocked_req = MagicMock(
            failure="net::ERR_FAILED: something",
            url="http://test.com",
        )
        req_failed_handler(blocked_req)

        # Other failure (should log warning)
        failed_req = MagicMock(
            failure="net::ERR_CONNECTION_REFUSED",
            url="http://test.com",
        )
        req_failed_handler(failed_req)

    # Test network interceptor route handler
    route_handlers = []
    mock_page.route = AsyncMock(
        side_effect=lambda pattern, handler: route_handlers.append(handler),
    )
    mock_provider = MagicMock()
    mock_provider.is_allowed_domain.return_value = False

    await _setup_network_interceptors(mock_page, mock_provider)
    assert len(route_handlers) == 1
    route_handler = route_handlers[0]

    # Case A: Blocked resource type (image)
    route_img = MagicMock()
    route_img.request.resource_type = "image"
    route_img.request.url = "https://www.eventbrite.ca/image.png"
    route_img.abort = AsyncMock()
    await route_handler(route_img)
    route_img.abort.assert_awaited_once()

    # Case B: Disallowed domain
    mock_provider.is_allowed_domain.return_value = False
    route_ext = MagicMock()
    route_ext.request.resource_type = "document"
    route_ext.request.url = "https://evil.com/page"
    route_ext.abort = AsyncMock()
    await route_handler(route_ext)
    route_ext.abort.assert_awaited_once()

    # Case C: Allowed domain & resource
    mock_provider.is_allowed_domain.return_value = True
    route_ok = MagicMock()
    route_ok.request.resource_type = "document"
    route_ok.request.url = "https://www.eventbrite.ca/page"
    route_ok.continue_ = AsyncMock()
    await route_handler(route_ok)
    route_ok.continue_.assert_awaited_once()

    # Case D: Exception handling inside route_handler (triggers suppress block)
    class ExplodingRoute:
        def __init__(self) -> None:
            self.continue_ = AsyncMock()

        @property
        def request(self) -> MagicMock:
            msg = "Simulated route error"
            raise PlaywrightError(msg)

    route_err = ExplodingRoute()
    await route_handler(route_err)  # type: ignore[arg-type]
    route_err.continue_.assert_awaited_once()


@pytest.mark.asyncio
async def test_fetch_page_content_null_response() -> None:
    """Verify fetch_page_content handles navigation returning None response."""
    mock_page = MagicMock()
    mock_page.on = MagicMock()
    mock_page.route = AsyncMock()
    mock_page.add_init_script = AsyncMock()
    mock_page.unroute_all = AsyncMock()
    mock_page.close = AsyncMock()
    mock_page.content = AsyncMock(
        return_value="<html>None Response Page</html>",
    )
    mock_page.goto = AsyncMock(return_value=None)  # Response is None

    mock_context = AsyncMock()
    mock_context.new_page = AsyncMock(return_value=mock_page)

    mock_provider = MagicMock()
    mock_provider.is_allowed_domain.return_value = True
    mock_provider.smart_wait_for_page = AsyncMock()

    result = await fetch_page_content(
        "https://www.eventbrite.ca/e/test-event",
        timeout=1000,
        context=mock_context,
        provider=mock_provider,
    )

    assert result == "<html>None Response Page</html>"


def test_save_html_to_temp_exception(tmp_path: Path) -> None:
    """Verify exception during HTML saving is caught and logged."""
    provider = EventbriteProvider()
    test_url = "https://www.eventbrite.ca/e/cool-event-tickets-99999"
    test_content = "<html><body><h1>Test Event</h1></body></html>"

    with patch.object(
        provider,
        "get_temporary_directory",
        side_effect=OSError("Disk full"),
    ):
        # Should catch the exception internally and log it without crashing
        _save_html_to_temp(test_url, test_content, provider)
