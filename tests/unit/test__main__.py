# tests/unit/test__main__.py
# SPDX-FileCopyrightText: 2026 Sebastien Lenard <sebastien.lenard@gmail.com> and Contributors
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for the Click CLI runner module (__main__.py)."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import click
import pytest
from click.testing import CliRunner

from eventus_publicus.__main__ import (
    _daterange,
    _get_default_date_range,
    _validate_date,
    main,
)
from eventus_publicus.schemas.event import Event
from eventus_publicus.services.date_range_pipeline import PipelineOptions


def test_get_default_date_range() -> None:
    """Verify _get_default_date_range returns valid YYYY-MM-DD Monday and Sunday."""
    start, end = _get_default_date_range()
    dt_start = datetime.strptime(start, "%Y-%m-%d").replace(tzinfo=UTC)
    dt_end = datetime.strptime(end, "%Y-%m-%d").replace(tzinfo=UTC)
    assert dt_start.weekday() == 0  # Monday
    assert dt_end.weekday() == 6  # Sunday
    assert (dt_end - dt_start).days == 6


def test_daterange() -> None:
    """Verify _daterange generates correct sequence of dates."""
    dates = _daterange("2026-08-01", "2026-08-03")
    assert dates == ["2026-08-01", "2026-08-02", "2026-08-03"]


def test_validate_date() -> None:
    """Verify _validate_date handles valid YYYY-MM-DD and raises BadParameter."""
    ctx = MagicMock(spec=click.Context)
    ctx.command = None
    param = MagicMock(spec=click.Parameter)

    assert _validate_date(ctx, param, None) is None
    assert _validate_date(ctx, param, "2026-08-01") == "2026-08-01"

    with pytest.raises(click.BadParameter, match="Invalid date format"):
        _validate_date(ctx, param, "01-08-2026")


def test_cli_main_invalid_date_range() -> None:
    """Verify CLI raises BadParameter when start date is after end date."""
    runner = CliRunner()
    result = runner.invoke(
        main,
        ["--start", "2026-08-10", "--end", "2026-08-01"],
    )
    assert result.exit_code != 0
    assert "cannot be after end date" in result.output


def test_cli_main_no_events() -> None:
    """Verify CLI handles zero events found gracefully."""
    runner = CliRunner()
    with patch(
        "eventus_publicus.__main__.scrape_events_for_date_range",
        new_callable=AsyncMock,
        return_value={"events": []},
    ):
        result = runner.invoke(
            main,
            ["--start", "2026-08-01", "--end", "2026-08-01"],
        )
        assert result.exit_code == 0
        assert "No events were found" in result.output


def test_cli_main_success() -> None:
    """Verify CLI executes pipeline successfully and generates reports."""
    runner = CliRunner()
    event = Event(
        date="2026-08-01",
        time="19:00",
        title="CLI Event",
        link="https://example.com/cli",
    )

    async def mock_scrape_with_progress(
        *args: object,
        **kwargs: object,
    ) -> dict[str, list[Event]]:
        options = kwargs.get("options")
        if isinstance(options, PipelineOptions) and options.on_progress:
            options.on_progress("2026-08-01", 1, 1, 1, 1)
        return {"events": [event]}

    with (
        patch(
            "eventus_publicus.__main__.scrape_events_for_date_range",
            side_effect=mock_scrape_with_progress,
        ),
        patch(
            "eventus_publicus.__main__.generate_markdown_report",
        ) as mock_md,
        patch(
            "eventus_publicus.__main__.generate_html_report",
        ) as mock_html,
        patch(
            "eventus_publicus.__main__.setup_logging",
        ) as mock_setup_log,
    ):
        result = runner.invoke(
            main,
            [
                "--start",
                "2026-08-01",
                "--end",
                "2026-08-01",
                "--cache",
                "--enrich",
                "--log-level",
                "INFO",
            ],
        )
        assert result.exit_code == 0
        mock_setup_log.assert_called_once()
        mock_md.assert_called_once()
        mock_html.assert_called_once()
        assert "Success! Processed 1 events." in result.output
