# src/eventus-publicus/utils/config.py
# SPDX-FileCopyrightText: 2026 Sebastien Lenard <sebastien.lenard@gmail.com> and Contributors
# SPDX-License-Identifier: Apache-2.0
"""Configuration module using Pydantic-Settings to validate environment variables."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class AppConfig(BaseSettings):
    """Application settings loaded from environment variables or .env file."""

    tmp_subfolder: str = "{provider}-eventus-publicus"
    playwright_wait_timeout_ms: int = 5000
    output_filename: str = "{provider}-{location}-events.{ext}"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


# Global configuration instance
settings = AppConfig()
