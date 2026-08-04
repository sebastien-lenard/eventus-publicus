# tests/conftest.py
# SPDX-FileCopyrightText: 2026 Sebastien Lenard <sebastien.lenard@gmail.com> and Contributors
# SPDX-License-Identifier: Apache-2.0
"""Global test fixtures and testing configuration."""

import logging
import socket
from collections.abc import Generator
from pathlib import Path
from unittest.mock import patch

import pytest

from eventus_publicus.utils.config import AppConfig, create_config


def pytest_collection_modifyitems(
    config: pytest.Config,
    items: list[pytest.Item],
) -> None:
    """Assign 'unit' marker to any test without 'e2e' or 'integration' markers."""
    for item in items:
        has_other_marker = any(
            item.get_closest_marker(name) for name in ["e2e", "integration"]
        )

        if not has_other_marker:
            item.add_marker(pytest.mark.unit)


@pytest.fixture(autouse=True)
def block_network_calls(
    request: pytest.FixtureRequest,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Prevent any outbound network requests during unit test execution.

    while allowing local loopback and tests marked with 'integration' or 'e2e'.
    """
    if request.node.get_closest_marker(
        "integration",
    ) or request.node.get_closest_marker("e2e"):
        return

    original_connect = socket.socket.connect

    def constrained_connect(
        self: socket.socket,
        address: tuple[str | bytes, int] | str,
        *args: object,
        **kwargs: object,
    ) -> None:
        if isinstance(address, tuple) and len(address) > 0:
            host = address[0]
            if host in ("127.0.0.1", "localhost", "::1", b"127.0.0.1"):
                return original_connect(self, address, *args, **kwargs)

        err_msg = "Network call attempted during isolated unit test execution."
        raise RuntimeError(err_msg)

    monkeypatch.setattr(socket.socket, "connect", constrained_connect)


@pytest.fixture(autouse=True)
def assert_logging_integrity(
    caplog: pytest.LogCaptureFixture,
) -> Generator[None, None, None]:
    """Verify log propagation integrity at the end of every test execution."""
    yield

    caplog.set_level(logging.INFO)
    canary_message = "LOGGING_INTEGRITY_CHECK_CANARY_TOKEN"

    logging.getLogger("eventus_publicus").info(canary_message)

    if canary_message not in caplog.text:
        err_msg = (
            (
                "CRITICAL: This test broke the global logging propagation! "
                "This usually happens when `setup_logging()` or `logging.basicConfig()`"
                " is called by the production code without being mocked. "
                "Please ensure you apply a proper patch/mock in this test script."
            ),
        )
        raise AssertionError(err_msg)


@pytest.fixture
def test_config(tmp_path: Path) -> Generator[AppConfig, None, None]:
    """Provide a configuration isolated."""
    config_instance = create_config()
    test_config_obj = config_instance.model_copy()

    with patch(
        "src.eventus_publicus.utils.config.get_config",
        return_value=test_config_obj,
    ):
        yield test_config_obj
