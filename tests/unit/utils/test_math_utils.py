# tests/unit/utils/test_math_utils.py
# SPDX-FileCopyrightText: 2026 Sebastien Lenard <sebastien.lenard@gmail.com> and Contributors
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for the math utilities module."""

from eventus_publicus.utils.math_utils import get_backoff_jitter


def test_get_backoff_jitter_default_bounds() -> None:
    """Verify get_backoff_jitter returns a float within default [0.0, 1.0] bounds."""
    for _ in range(50):
        val = get_backoff_jitter()
        assert isinstance(val, float)
        assert 0.0 <= val <= 1.0


def test_get_backoff_jitter_custom_bounds() -> None:
    """Verify get_backoff_jitter respects custom low and high bounds."""
    for _ in range(50):
        val = get_backoff_jitter(5.0, 10.0)
        assert isinstance(val, float)
        assert 5.0 <= val <= 10.0
