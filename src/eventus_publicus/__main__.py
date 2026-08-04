# src/eventus_publicus/__main__.py
# SPDX-FileCopyrightText: 2026 Sebastien Lenard <sebastien.lenard@gmail.com> and Contributors
# SPDX-License-Identifier: Apache-2.0
"""Command Line Interface (CLI) runner using Click and Rich."""

import asyncio
import logging
from datetime import UTC, datetime, timedelta

import click
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)

from eventus_publicus.services.date_range_pipeline import (
    PipelineOptions,
    scrape_events_for_date_range,
)
from eventus_publicus.utils.config import get_config
from eventus_publicus.utils.logging_config import setup_logging
from eventus_publicus.writers.html_writer import generate_html_report
from eventus_publicus.writers.markdown_writer import generate_markdown_report


def _get_default_date_range() -> tuple[str, str]:
    """Calculate the coming Monday and following Sunday relative to today."""
    today = datetime.now(tz=UTC)
    days_until_next_monday = (7 - today.weekday()) % 7
    if days_until_next_monday == 0:
        days_until_next_monday = 7

    next_monday_dt = today + timedelta(days=days_until_next_monday)
    following_sunday_dt = next_monday_dt + timedelta(days=6)

    return (
        next_monday_dt.strftime("%Y-%m-%d"),
        following_sunday_dt.strftime("%Y-%m-%d"),
    )


def _daterange(start_date: str, end_date: str) -> list[str]:
    """Generate a list of date strings (YYYY-MM-DD) from start to end inclusive."""
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


def _validate_date(
    ctx: click.Context,
    param: click.Parameter,
    value: str | None,
) -> str | None:
    """Validate that the given string matches YYYY-MM-DD format."""
    if value is None:
        return None

    try:
        datetime.strptime(value, "%Y-%m-%d").replace(
            tzinfo=UTC,
        )
    except ValueError as err:
        msg = f"Invalid date format: '{value}'. Expected YYYY-MM-DD."
        raise click.BadParameter(msg, ctx=ctx, param=param) from err
    return value


@click.command()
@click.option(
    "--start",
    type=click.STRING,
    callback=_validate_date,
    default=None,
    help="Start date (YYYY-MM-DD). Defaults to next Monday.",
)
@click.option(
    "--end",
    type=click.STRING,
    callback=_validate_date,
    default=None,
    help="End date (YYYY-MM-DD). Defaults to following Sunday.",
)
@click.option(
    "--country",
    type=click.STRING,
    default=None,
    help="Country or state code (e.g., canada, co). Defaults to config/.env value.",
)
@click.option(
    "--city",
    type=click.STRING,
    default=None,
    help="City or town name (e.g., calgary, denver). Defaults to config/.env value.",
)
@click.option(
    "--cache/--no-cache",
    default=True,
    help="Use cached JSON results if available (default: enabled).",
)
@click.option(
    "--enrich/--no-enrich",
    default=True,
    help=("Enrich event details by scraping individual links (default: enabled)."),
)
@click.option(
    "--log-level",
    type=click.Choice(
        ["DEBUG", "INFO", "WARNING", "ERROR"],
        case_sensitive=False,
    ),
    default="WARNING",
    help="Set the logging level for diagnostics (default: WARNING).",
)
def main(**_kwargs: object) -> None:
    """Scrape, filter, enrich, and report events for a date range and location."""
    ctx = click.get_current_context()
    start = ctx.params.get("start")
    end = ctx.params.get("end")
    country = ctx.params.get("country")
    city = ctx.params.get("city")
    cache = ctx.params.get("cache", True)
    enrich = ctx.params.get("enrich", True)
    log_level = ctx.params.get("log_level", "WARNING")

    numeric_level = getattr(logging, str(log_level).upper(), logging.WARNING)
    setup_logging(level=numeric_level)

    config = get_config()

    default_start, default_end = _get_default_date_range()
    start_date = start or default_start
    end_date = end or default_end

    target_country = country if country is not None else config.default_country
    target_city = city if city is not None else config.default_city

    if start_date > end_date:
        err_msg = f"Start date ({start_date}) cannot be after end date ({end_date})."
        raise click.BadParameter(err_msg)

    click.echo(f"📅 Date Range: {start_date} to {end_date}")
    click.echo(
        f"📍 Location: {f'{target_country} / ' if target_country else ''}{target_city}",
    )
    click.echo(f"📦 Cache: {'Enabled' if cache else 'Disabled'}")
    click.echo(f"🔍 Enrichment: {'Enabled' if enrich else 'Disabled'}")
    click.echo(f"📝 Log Level: {str(log_level).upper()}")
    click.echo("-" * 40)

    async def run_pipeline() -> dict:
        dates = _daterange(start_date, end_date)
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TextColumn("•"),
            TimeElapsedColumn(),
            TextColumn("left:"),
            TimeRemainingColumn(),
        ) as progress:
            task = progress.add_task(
                "[cyan]Initializing scraper...",
                total=len(dates),
            )

            def update_progress(
                date_str: str,
                page_num: int,
                total_pages: int,
                total_dates: int,
                date_idx: int,
            ) -> None:
                page_progress = (page_num - 1) / max(total_pages, 1)
                fractional_completion = (date_idx - 1) + page_progress
                progress.update(
                    task,
                    total=total_dates,
                    completed=fractional_completion,
                    description=(
                        f"[cyan]Processing Date: {date_str} "
                        f"| Page {page_num}/{total_pages}"
                    ),
                )

            result = await scrape_events_for_date_range(
                start_date,
                end_date,
                options=PipelineOptions(
                    enrich=enrich,
                    use_cache=cache,
                    country=target_country,
                    city=target_city,
                    on_progress=update_progress,
                ),
                config=config,
            )
            progress.update(
                task,
                completed=len(dates),
                description="[green]Scraping complete!",
            )
            return result

    full_result_dict = asyncio.run(run_pipeline())
    events = full_result_dict.get("events", [])

    if not events:
        click.echo(
            "No events were found across the specified date range or location.",
            err=True,
        )
        return

    generate_markdown_report(
        events_data=full_result_dict,
        city=target_city,
        config=config,
    )
    generate_html_report(events_data=full_result_dict, city=target_city, config=config)

    click.echo(f"\n✨ Success! Processed {len(events)} events.")
    click.echo("📁 Reports successfully saved to your Downloads folder.")


if __name__ == "__main__":
    main()
