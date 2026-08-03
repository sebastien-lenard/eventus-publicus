# src/eventus_publicus/utils/date_utils.py
# SPDX-FileCopyrightText: 2026 Sebastien Lenard <sebastien.lenard@gmail.com> and Contributors
# SPDX-License-Identifier: Apache-2.0
"""Utility functions for date manipulation and formatting."""

from datetime import UTC, datetime


def get_day_initial(date_str: str) -> str:
    """Return a single-letter day-of-week indicator.

    Mappings:
    - Monday -> M
    - Tuesday -> T
    - Wednesday -> W
    - Thursday -> H (Distinguished from Tuesday)
    - Friday -> F
    - Saturday -> S
    - Sunday -> U (Distinguished from Saturday)
    """
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=UTC)
        # Python weekday(): 0=Mon, 1=Tue, 2=Wed, 3=Thu, 4=Fri, 5=Sat, 6=Sun
        mapping = {
            0: "M",
            1: "T",
            2: "W",
            3: "H",
            4: "F",
            5: "S",
            6: "U",
        }
        return mapping.get(dt.weekday(), "")
    except ValueError:
        return ""
