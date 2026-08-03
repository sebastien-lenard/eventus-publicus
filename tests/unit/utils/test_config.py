# tests/unit/utils/test_config.py
# SPDX-FileCopyrightText: 2026 Sebastien Lenard <sebastien.lenard@gmail.com> and Contributors
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for the configuration module."""

from eventus_publicus.utils.config import (
    AppConfig,
    create_config,
    get_config,
    settings,
)


def test_app_config_defaults() -> None:
    """Verify AppConfig initializes with expected default settings."""
    config = AppConfig()
    assert config.tmp_subfolder == "{provider}-eventus-publicus"
    assert config.playwright_wait_timeout_ms == 5000
    assert config.output_filename == "{provider}-{location}-events.{ext}"


def test_create_config_with_overrides() -> None:
    """Verify create_config correctly applies custom keyword arguments."""
    config = create_config(
        tmp_subfolder="custom-sub",
        playwright_wait_timeout_ms=10000,
        output_filename="custom.{ext}",
    )
    assert config.tmp_subfolder == "custom-sub"
    assert config.playwright_wait_timeout_ms == 10000
    assert config.output_filename == "custom.{ext}"


def test_get_config_caching() -> None:
    """Verify get_config returns an AppConfig instance and caches it via lru_cache."""
    config1 = get_config()
    config2 = get_config()
    assert isinstance(config1, AppConfig)
    assert config1 is config2


def test_settings_global_instance() -> None:
    """Verify global settings object is an instance of AppConfig."""
    assert isinstance(settings, AppConfig)
