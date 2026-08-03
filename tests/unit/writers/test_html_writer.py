# tests/unit/writers/test_html_writer.py
# SPDX-FileCopyrightText: 2026 Sebastien Lenard <sebastien.lenard@gmail.com> and Contributors
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for the HTML writer module."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from eventus_publicus.schemas.event import Event
from eventus_publicus.writers.html_writer import (
    _clean_text,
    _format_description_html,
    generate_html_report,
)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (None, ""),
        ("", ""),
        ("<p>Hello <b>World</b></p>", "Hello World"),
        ("   Multiple   Spaces   ", "Multiple   Spaces"),
    ],
)
def test_clean_text(text: str | None, expected: str) -> None:
    """Verify _clean_text strips HTML tags and normalizes whitespace."""
    assert _clean_text(text) == expected


@pytest.mark.parametrize(
    ("html_content", "max_length", "expected_substrings"),
    [
        ("", 10, [""]),
        ("Short text", 20, ["Short text"]),
        (
            (
                "This is a very long description that definitely exceeds the maximum"
                " length allowed for the preview text."
            ),
            20,
            ["...", "<details>", "<summary>Read more</summary>"],
        ),
    ],
)
def test_format_description_html(
    html_content: str,
    max_length: int,
    expected_substrings: list[str],
) -> None:
    """Verify _format_description_html formats short text vs collapsible preview."""
    result = _format_description_html(html_content, max_length=max_length)
    for sub in expected_substrings:
        assert sub in result


def test_generate_html_report_success(tmp_path: Path) -> None:
    """Verify generate_html_report successfully creates the HTML report file."""
    event_with_prices = Event(
        date="2026-08-01",
        time="19:00",
        title="Concert & Show",
        location="Calgary Hall",
        organizer="Org Inc",
        full_address="123 Street",
        description="Great event description here.",
        low_price=10.5,
        high_price=50.0,
        link="https://example.com/tickets",
    )
    event_minimal = Event(
        date="2026-08-02",
        time="20:00",
        title="Minimal Event",
        link="",
    )

    mock_provider = MagicMock()
    mock_provider.get_report_filenames.return_value = ("report.md", "report.html")

    with patch(
        "eventus_publicus.writers.html_writer.get_downloads_folder",
        return_value=tmp_path,
    ):
        generate_html_report(
            events_data={"events": [event_with_prices, event_minimal]},
            provider=mock_provider,
        )

        output_file = tmp_path / "report.html"
        assert output_file.exists()
        content = output_file.read_text(encoding="utf-8")
        assert "Concert &amp; Show" in content
        assert "$10.50" in content
        assert "$50.00" in content
        assert "Minimal Event" in content


def test_generate_html_report_oserror(tmp_path: Path) -> None:
    """Verify generate_html_report raises OSError and logs when write fails."""
    event = Event(
        date="2026-08-01",
        time="19:00",
        title="Event",
        link="https://example.com",
    )
    mock_provider = MagicMock()
    mock_provider.get_report_filenames.return_value = ("report.md", "report.html")

    with (
        patch(
            "eventus_publicus.writers.html_writer.get_downloads_folder",
            return_value=tmp_path,
        ),
        patch.object(
            Path,
            "write_text",
            side_effect=OSError("Disk full"),
        ),
        pytest.raises(OSError, match="Disk full"),
    ):
        generate_html_report(
            events_data={"events": [event]},
            provider=mock_provider,
        )
