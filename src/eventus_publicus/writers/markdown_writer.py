# src/eventus_publicus/writers/markdown_writer.py
# SPDX-FileCopyrightText: 2026 Sebastien Lenard <sebastien.lenard@gmail.com> and Contributors
# SPDX-License-Identifier: Apache-2.0
"""Module to generate and write formatted markdown event reports."""

import logging
from pathlib import Path

from bs4 import BeautifulSoup

from eventus_publicus.providers.base import EventProvider
from eventus_publicus.providers.eventbrite import EventbriteProvider
from eventus_publicus.schemas.event import Event
from eventus_publicus.utils.config import AppConfig
from eventus_publicus.utils.date_utils import get_day_initial

logger = logging.getLogger(__name__)


def get_downloads_folder() -> Path:
    """Return the platform-specific user Downloads directory."""
    home = Path.home()
    if (downloads := home / "Downloads").exists():
        return downloads
    return home


def _clean_text_for_table(text: str | None) -> str:
    """Strip HTML tags, replace pipes, and clean whitespace for markdown cells."""
    if not text:
        return ""

    soup = BeautifulSoup(text, "html.parser")
    cleaned = soup.get_text(separator=" ", strip=True)

    return cleaned.replace("|", "-")


def _format_description_with_dropdown(
    html_content: str,
    max_length: int = 150,
) -> str:
    """Format description with short preview and native HTML dropdown."""
    if not html_content:
        return ""

    full_text = _clean_text_for_table(html_content)

    if len(full_text) <= max_length:
        return full_text

    preview_text = full_text[:max_length].rstrip() + "..."
    remaining_text = full_text[max_length:].lstrip()

    return (
        f"{preview_text} "
        f"<details>"
        f"<summary>Read more</summary>"
        f"<span>{remaining_text}</span>"
        f"</details>"
    )


def generate_markdown_report(
    *,
    events_data: dict[str, list[Event]],
    config: AppConfig | None = None,
    provider: EventProvider | None = None,
) -> None:
    """Generate and write the sorted markdown event report to downloads folder."""
    active_provider = provider or EventbriteProvider()
    filename, _ = active_provider.get_report_filenames("calgary", config=config)
    download_dir = get_downloads_folder()
    output_path = download_dir / filename

    header_cols = (
        "| Day | Date | Time | Location | Title | Low_price | "
        "High_price | Organizer | Full_address | Description | Link |"
    )
    separator_cols = (
        "| :---: | :--- | :--- | :--- | :--- | :--- | :--- | "
        ":--- | :--- | :--- | :--- |"
    )

    lines = [
        f"# {filename}",
        "",
        header_cols,
        separator_cols,
    ]

    for ev in events_data.get("events", []):
        day_str = get_day_initial(ev.date)
        date_str = _clean_text_for_table(ev.date)
        time_str = _clean_text_for_table(ev.time)
        location_str = _clean_text_for_table(ev.location)
        title_str = _clean_text_for_table(ev.title)
        organizer_str = _clean_text_for_table(ev.organizer)
        address_str = _clean_text_for_table(ev.full_address)
        desc_cell = _format_description_with_dropdown(ev.description)
        low_p = f"${ev.low_price:.2f}" if ev.low_price is not None else ""
        high_p = f"${ev.high_price:.2f}" if ev.high_price is not None else ""

        link_html = (
            f'<a href="{ev.link}" target="_blank" rel="noopener noreferrer">Link</a>'
            if ev.link
            else ""
        )

        lines.append(
            f"| {day_str} | {date_str} | {time_str} | {location_str} | {title_str} | "
            f"{low_p} | {high_p} | {organizer_str} | "
            f"{address_str} | {desc_cell} | {link_html} |",
        )

    content = "\n".join(lines)
    try:
        output_path.write_text(content, encoding="utf-8")
    except OSError:
        logger.exception("Failed to write markdown output to %s", output_path)
        raise
    else:
        logger.info("Markdown report successfully written to %s", output_path)
