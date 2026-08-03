# src/eventus_publicus/fetchers/scraper.py
# SPDX-FileCopyrightText: 2026 Sebastien Lenard <sebastien.lenard@gmail.com> and Contributors
# SPDX-License-Identifier: Apache-2.0

"""Asynchronous web scraper using pure Playwright and BeautifulSoup for parsing."""

import asyncio
import logging
import sys
import time
from collections.abc import Awaitable, Callable
from contextlib import suppress
from functools import wraps
from typing import ParamSpec, TypeVar
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from playwright.async_api import BrowserContext, Page, Request, Route, async_playwright
from playwright.async_api import Error as PlaywrightError

from eventus_publicus.providers.base import EventProvider
from eventus_publicus.providers.eventbrite import EventbriteProvider
from eventus_publicus.utils.config import AppConfig
from eventus_publicus.utils.math_utils import get_backoff_jitter

logger = logging.getLogger(__name__)

MIN_REQUEST_INTERVAL_SECONDS = 1.0

P = ParamSpec("P")
R = TypeVar("R")


def async_retry(
    retries: int = 3,
    base_delay: float = 2.0,
    max_delay: float = 30.0,
    exceptions: tuple[type[Exception], ...] = (PlaywrightError, OSError),
) -> Callable[[Callable[P, Awaitable[R]]], Callable[P, Awaitable[R]]]:
    """Provide exponential backoff with randomized jitter for async functions."""

    def decorator(func: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
        @wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            attempt = 0
            while True:
                try:
                    return await func(*args, **kwargs)
                except exceptions as err:
                    attempt += 1
                    if attempt > retries:
                        logger.exception(
                            "Function '%s' failed after maximum %d retries.",
                            func.__name__,
                            retries,
                        )
                        raise

                    exponential = base_delay * (2 ** (attempt - 1))
                    jitter = get_backoff_jitter(0.0, 1.0)
                    sleep_time = min(max_delay, exponential + jitter)

                    logger.warning(
                        (
                            "Attempt %d/%d failed for '%s' due to %s. "
                            "Retrying in %.2f seconds..."
                        ),
                        attempt,
                        retries,
                        func.__name__,
                        err.__class__.__name__,
                        sleep_time,
                    )
                    await asyncio.sleep(sleep_time)

        return wrapper

    return decorator


class DomainRateLimiter:
    """Thread-safe and async-safe rate limiter enforcing delays between requests."""

    def __init__(self, min_interval: float = MIN_REQUEST_INTERVAL_SECONDS) -> None:
        self.min_interval = min_interval
        self._last_request_times: dict[str, float] = {}
        self._lock = asyncio.Lock()

    async def wait_if_needed(self, url: str) -> None:
        """Check last request time for domain and sleep if called quickly."""
        parsed_url = urlparse(url)
        domain = parsed_url.netloc.lower()

        if not domain:
            return

        async with self._lock:
            now = time.monotonic()
            last_time = self._last_request_times.get(domain, 0.0)
            elapsed = now - last_time

            if elapsed < self.min_interval:
                wait_time = self.min_interval - elapsed
                logger.info(
                    "Rate limit active for domain '%s'. Waiting for %.2f seconds...",
                    domain,
                    wait_time,
                )
                await asyncio.sleep(wait_time)

            self._last_request_times[domain] = time.monotonic()


_rate_limiter = DomainRateLimiter()


def _setup_page_event_listeners(page: Page) -> None:
    """Attach logging event listeners to Playwright page."""
    page.on(
        "request",
        lambda req: logger.debug("NETWORK REQUEST: %s", req.url),
    )
    page.on(
        "response",
        lambda res: logger.debug(
            "NETWORK RESPONSE [%s]: %s",
            res.status,
            res.url,
        ),
    )

    def handle_request_failed(req: Request) -> None:
        if req.failure and "net::ERR_FAILED" in req.failure:
            logger.debug("INTENTIONALLY BLOCKED REQUEST: %s", req.url)
            return
        logger.warning(
            "NETWORK REQUEST FAILED: %s (Reason: %s)",
            req.url,
            req.failure,
        )

    page.on("requestfailed", handle_request_failed)


async def _setup_network_interceptors(
    page: Page,
    provider: EventProvider,
) -> None:
    """Block unneeded resource types and external domains safely."""

    async def route_handler(route: Route) -> None:
        try:
            req = route.request
            url = req.url
            parsed = urlparse(url)
            domain = parsed.netloc.lower()

            if req.resource_type in {"image", "media", "font", "stylesheet"}:
                await route.abort()
                return

            if domain and not provider.is_allowed_domain(domain):
                await route.abort()
                return

            await route.continue_()
        except (PlaywrightError, OSError):
            with suppress(Exception):
                await route.continue_()

    await page.route("**/*", route_handler)


async def _apply_antibot_overrides(page: Page) -> None:
    """Inject native anti-bot and CDP overrides into the page."""
    await page.add_init_script(
        """
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined
        });
        window.chrome = { runtime: {} };
        Object.defineProperty(navigator, 'languages', {
            get: () => ['en-US', 'en']
        });
        Object.defineProperty(navigator, 'plugins', {
            get: () => [1, 2, 3, 4, 5]
        });
    """,
    )


def _save_html_to_temp(
    url: str,
    content: str,
    provider: EventProvider,
    config: AppConfig | None = None,
) -> None:
    """Save fetched HTML content into the provider temporary directory."""
    if not content:
        return
    try:
        clean_url = url.split("?", maxsplit=1)[0].split("#", maxsplit=1)[0]
        last_segment = clean_url.rstrip("/").split("/")[-1]
        filename = f"{last_segment or 'index'}.html"

        tmp_dir = provider.get_temporary_directory(config=config)

        file_path = tmp_dir / filename
        file_path.write_text(content, encoding="utf-8")
        logger.debug("Saved fetched HTML content to: %s", file_path.resolve())
    except Exception:
        logger.exception("Failed to save HTML content to temporary directory")


async def _fetch_with_context(
    url: str,
    timeout: int,
    context: BrowserContext,
    provider: EventProvider,
    config: AppConfig | None = None,
) -> str:
    """Execute page fetching lifecycle using a shared Playwright context."""
    page = await context.new_page()
    try:
        _setup_page_event_listeners(page)
        await _setup_network_interceptors(page, provider)
        await _apply_antibot_overrides(page)

        logger.info("Executing page.goto() for: %s", url)
        response = await page.goto(
            url,
            timeout=timeout,
            wait_until="domcontentloaded",
        )

        if response:
            logger.debug(
                "Navigation responded with HTTP status code: %s",
                response.status,
            )
        else:
            logger.warning(
                "Navigation response object was None (potential redirect/block).",
            )

        await provider.smart_wait_for_page(page, url, config=config)

        content = await page.content()
        _save_html_to_temp(url, content, provider, config=config)

        await page.unroute_all(behavior="ignoreErrors")
        return content
    finally:
        await page.close()


@async_retry(retries=3, base_delay=2.0, max_delay=20.0)
async def fetch_page_content(
    url: str,
    timeout: int = 15000,
    context: BrowserContext | None = None,
    provider: EventProvider | None = None,
    config: AppConfig | None = None,
) -> str:
    """Fetch HTML content of a web page asynchronously with optimized waits."""
    logger.debug("-> Entering fetch_page_content() for URL: %s", url)

    active_provider = provider or EventbriteProvider()

    await _rate_limiter.wait_if_needed(url)

    if context is not None:
        return await _fetch_with_context(
            url,
            timeout,
            context,
            active_provider,
            config=config,
        )

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-infobars",
                "--disable-gpu",
            ],
        )
        ctx = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/126.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
        )

        try:
            content = await _fetch_with_context(
                url,
                timeout,
                ctx,
                active_provider,
                config=config,
            )
            logger.debug("<- Exiting fetch_page_content() successfully.")
            return content
        finally:
            await browser.close()


async def test_playwright_basic() -> bool:
    """Test if asynchronous Playwright functions properly using a basic URL."""
    test_url = "https://httpbin.org/html"
    logger.info("Running basic connectivity test on %s...", test_url)

    html_content = await fetch_page_content(test_url, timeout=10000)

    if not html_content:
        logger.warning(
            "TEST FAILURE: fetch_page_content returned empty content for %s",
            test_url,
        )
        return False

    logger.debug("Evaluating HTML content against expected assertion string...")
    expected_substring = "Herman Melville"
    if expected_substring in html_content:
        logger.info("Basic Playwright test PASSED.")
        return True

    logger.warning(
        "TEST FAILURE: Expected substring '%s' was not found in response HTML.",
        expected_substring,
    )
    logger.debug(
        "DUMPING RECEIVED HTML CONTENT (First 500 chars):\n%s",
        html_content[:500],
    )
    return False


async def main() -> None:
    """Execute asynchronous main routines for testing and reading target page."""
    logger.info("Starting scraper main routine execution.")

    if not await test_playwright_basic():
        logger.error("Aborting execution due to basic test failure.")
        sys.exit(1)

    logger.info("-" * 50)

    target_url = (
        "https://www.eventbrite.ca/e/"
        "la-elegancia-latina-summer-vibes-tickets-1993233171071"
        "?aff=ebdssbdestsearch"
    )

    html_content = await fetch_page_content(target_url, timeout=25000)

    if not html_content:
        logger.warning("Failed to retrieve HTML content from Eventbrite.")
        return

    soup = BeautifulSoup(html_content, "html.parser")
    title_tag = soup.find("title")

    if title_tag and title_tag.string:
        page_title = title_tag.string.strip()
        logger.info("Successfully extracted Title:\n-> %s", page_title)
    else:
        logger.warning("Could not locate a valid <title> tag in HTML content.")
        logger.debug(
            "DUMPING EVENTBRITE HTML CONTENT (First 500 chars):\n%s",
            html_content[:500],
        )


if __name__ == "__main__":
    with suppress(KeyboardInterrupt):
        asyncio.run(main())
