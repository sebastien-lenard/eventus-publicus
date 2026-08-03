# src/eventus_publicus/writers/html_writer.py
# SPDX-FileCopyrightText: 2026 Sebastien Lenard <sebastien.lenard@gmail.com> and Contributors
# SPDX-License-Identifier: Apache-2.0
"""Module to generate and write formatted HTML event reports."""

import html
import logging

from bs4 import BeautifulSoup

from eventus_publicus.providers.base import EventProvider
from eventus_publicus.providers.eventbrite import EventbriteProvider
from eventus_publicus.schemas.event import Event
from eventus_publicus.utils.config import AppConfig
from eventus_publicus.utils.date_utils import get_day_initial
from eventus_publicus.writers.markdown_writer import get_downloads_folder

logger = logging.getLogger(__name__)


def _clean_text(text: str | None) -> str:
    """Strip HTML tags and clean whitespace for HTML table cells."""
    if not text:
        return ""
    soup = BeautifulSoup(text, "html.parser")
    return soup.get_text(separator=" ", strip=True)


def _format_description_html(html_content: str, max_length: int = 150) -> str:
    """Format the description with a short preview and native drop-down."""
    if not html_content:
        return ""

    full_text = _clean_text(html_content)

    if len(full_text) <= max_length:
        return html.escape(full_text)

    preview_text = full_text[:max_length].rstrip() + "..."
    remaining_text = full_text[max_length:].lstrip()

    return (
        f"{html.escape(preview_text)} "
        f"<details>"
        f"<summary>Read more</summary>"
        f"<span>{html.escape(remaining_text)}</span>"
        f"</details>"
    )


def generate_html_report(
    *,
    events_data: dict[str, list[Event]],
    config: AppConfig | None = None,
    provider: EventProvider | None = None,
) -> None:
    """Generate and write the sorted HTML event report to the downloads folder."""
    active_provider = provider or EventbriteProvider()
    _, filename = active_provider.get_report_filenames("calgary", config=config)

    download_dir = get_downloads_folder()
    output_path = download_dir / filename

    rows = []
    for ev in events_data.get("events", []):
        day_str = html.escape(get_day_initial(ev.date))
        date_str = html.escape(_clean_text(ev.date))
        time_str = html.escape(_clean_text(ev.time))
        location_str = html.escape(_clean_text(ev.location))
        title_str = html.escape(_clean_text(ev.title))
        organizer_str = html.escape(_clean_text(ev.organizer))
        address_str = html.escape(_clean_text(ev.full_address))
        desc_cell = _format_description_html(ev.description)
        low_p = f"${ev.low_price:.2f}" if ev.low_price is not None else ""
        high_p = f"${ev.high_price:.2f}" if ev.high_price is not None else ""

        link_html = (
            f'<a href="{html.escape(ev.link)}" target="_blank" '
            f'rel="noopener noreferrer">Link</a>'
            if ev.link
            else ""
        )

        rows.append(
            f"    <tr>\n"
            f'      <td style="text-align: center; font-weight: bold;">{day_str}</td>\n'
            f"      <td>{date_str}</td>\n"
            f"      <td>{time_str}</td>\n"
            f"      <td>{location_str}</td>\n"
            f"      <td>{title_str}</td>\n"
            f"      <td>{low_p}</td>\n"
            f"      <td>{high_p}</td>\n"
            f"      <td>{organizer_str}</td>\n"
            f"      <td>{address_str}</td>\n"
            f"      <td>{desc_cell}</td>\n"
            f"      <td>{link_html}</td>\n"
            f"    </tr>",
        )

    table_rows = "\n".join(rows)

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Eventbrite Calgary Events Report</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI",
                         Roboto, Helvetica, Arial, sans-serif;
            margin: 20px;
            color: #333;
            background-color: #f9f9f9;
        }}
        h1 {{
            font-size: 1.5rem;
            color: #111;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            background: #fff;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            margin-top: 20px;
        }}
        th, td {{
            padding: 12px 15px;
            border-bottom: 1px solid #ddd;
            text-align: left;
            font-size: 0.9rem;
            vertical-align: top;
        }}
        th {{
            background-color: #f4f4f4;
            font-weight: 600;
            position: sticky;
            top: 0;
            z-index: 10;
            box-shadow: 0 2px 2px -1px rgba(0, 0, 0, 0.1);
        }}
        tr:hover {{
            background-color: #f1f1f1;
        }}
        details {{
            margin-top: 4px;
        }}
        summary {{
            cursor: pointer;
            color: #0066cc;
            font-size: 0.85rem;
        }}
    </style>
</head>
<body>
    <h1>Eventbrite Calgary Events Report</h1>
    <table>
        <thead>
            <tr>
                <th>Day</th>
                <th>Date</th>
                <th>Time</th>
                <th>Location</th>
                <th>Title</th>
                <th>Low Price</th>
                <th>High Price</th>
                <th>Organizer</th>
                <th>Full Address</th>
                <th>Description</th>
                <th>Link</th>
            </tr>
        </thead>
        <tbody>
{table_rows}
        </tbody>
    </table>
</body>
</html>
"""

    try:
        output_path.write_text(html_content, encoding="utf-8")
    except OSError:
        logger.exception("Failed to write HTML output to %s", output_path)
        raise
    else:
        logger.info("HTML report successfully written to %s", output_path)
