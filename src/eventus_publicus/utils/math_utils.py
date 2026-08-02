# src/eventus-publicus/utils/math_utils.py
# SPDX-FileCopyrightText: 2026 Sebastien Lenard <sebastien.lenard@gmail.com> and Contributors
# SPDX-License-Identifier: Apache-2.0
"""Mathematical and pseudo-random utility functions."""

import random


def get_backoff_jitter(low: float = 0.0, high: float = 1.0) -> float:
    """Return a non-cryptographic pseudo-random jitter value for backoff delays."""
    return random.uniform(low, high)  # noqa: S311
