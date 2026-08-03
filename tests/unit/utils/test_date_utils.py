# tests/unit/utils/test_date_utils.py
# SPDX-FileCopyrightText: 2026 Sebastien Lenard <sebastien.lenard@gmail.com> and Contributors
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for the date utilities module."""

import pytest

from eventus_publicus.utils.date_utils import get_day_initial


@pytest.mark.parametrize(
    ("date_str", "expected_initial"),
    [
        ("2026-08-03", "M"),  # Monday
        ("2026-08-04", "T"),  # Tuesday
        ("2026-08-05", "W"),  # Wednesday
        ("2026-08-06", "H"),  # Thursday
        ("2026-08-07", "F"),  # Friday
        ("2026-08-08", "S"),  # Saturday
        ("2026-08-09", "U"),  # Sunday
        ("invalid-date", ""),  # ValueError exception case
        ("", ""),
    ],
)
def test_get_day_initial(date_str: str, expected_initial: str) -> None:
    """Verify get_day_initial returns day mappings and handles invalid dates."""
    assert get_day_initial(date_str) == expected_initial
