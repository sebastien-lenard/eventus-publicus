# tests/unit/utils/test_logging_config.py
# SPDX-FileCopyrightText: 2026 Sebastien Lenard <sebastien.lenard@gmail.com> and Contributors
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for the logging configuration module."""

import logging
from unittest.mock import patch

import pytest

from eventus_publicus.utils.logging_config import setup_logging


@pytest.mark.parametrize(
    "level",
    [
        logging.DEBUG,
        logging.INFO,
        logging.WARNING,
        logging.ERROR,
    ],
)
def test_setup_logging(level: int) -> None:
    """Verify setup_logging configures root logging with correct level."""
    with patch(
        "eventus_publicus.utils.logging_config.logging.basicConfig",
    ) as mock_basic_config:
        setup_logging(level=level)

        mock_basic_config.assert_called_once()
        _, kwargs = mock_basic_config.call_args

        assert kwargs["level"] == level
        assert kwargs["format"] == "%(message)s"
        assert kwargs["datefmt"] == "[%X]"
        assert kwargs["force"] is True
        assert len(kwargs["handlers"]) == 1
