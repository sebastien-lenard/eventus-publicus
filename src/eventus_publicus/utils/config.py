# src/eventus_publicus/utils/config.py
# SPDX-FileCopyrightText: 2026 Sebastien Lenard <sebastien.lenard@gmail.com> and Contributors
# SPDX-License-Identifier: Apache-2.0
"""Configuration module using Pydantic-Settings to validate environment variables."""

from functools import lru_cache
from typing import Any

from pydantic_settings import BaseSettings, SettingsConfigDict


class AppConfig(BaseSettings):
    """Application settings loaded from environment variables or .env file."""

    tmp_subfolder: str = "{provider}-eventus-publicus"
    playwright_wait_timeout_ms: int = 5000
    output_filename: str = "{provider}-{location}-events.{ext}"
    default_country: str | None = "canada"
    default_city: str = "calgary"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


def create_config(**kwargs: Any) -> AppConfig:  # noqa: ANN401
    """Instantiate a fresh configuration payload for runtime or isolation testing."""
    return AppConfig(**kwargs)


@lru_cache(maxsize=1)
def get_config() -> AppConfig:
    """Retrieve the globally cached configuration configuration.

    WARNING: Should either be called in cli.py or inside class methods, not outside, so
    as to make tests not interfering with production directories.
    """
    return create_config()


settings = get_config()
