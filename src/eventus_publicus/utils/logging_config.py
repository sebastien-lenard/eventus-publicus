# src/eventus_publicus/utils/logging_config.py
# SPDX-FileCopyrightText: 2026 Sebastien Lenard <sebastien.lenard@gmail.com> and Contributors
# SPDX-License-Identifier: Apache-2.0
"""Centralized logging configuration module using Rich handler."""

import logging

from rich.logging import RichHandler


def setup_logging(level: int = logging.WARNING) -> None:
    """Configure root logger with RichHandler for clean CLI rendering."""
    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(rich_tracebacks=True, markup=True)],
        force=True,
    )
