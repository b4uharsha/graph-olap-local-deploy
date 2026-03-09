"""Configuration management using pydantic-settings.

Configuration is loaded from environment variables with sensible defaults.
All sensitive values (passwords, tokens) must be provided via environment.

Environment variables for K8s Export Worker (ADR-025):
- GCP_PROJECT: GCP project ID
- STARBURST_URL, STARBURST_USER, STARBURST_PASSWORD: Starburst auth
- STARBURST_CLIENT_TAGS: Client tags for resource group routing (default: graph-olap-export)
- STARBURST_SOURCE: Source identifier (default: graph-olap-export-worker)
- CONTROL_PLANE_URL: Control Plane internal URL
- POLL_INTERVAL_SECONDS: Main loop interval (default: 5)
- EMPTY_POLL_BACKOFF_SECONDS: Backoff when no work (default: 10)
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class StarburstConfig(BaseSettings):
    """Starburst connection configuration."""

    model_config = SettingsConfigDict(env_prefix="STARBURST_")

    url: str = Field(description="Starburst REST API URL")
    user: str = Field(description="Starburst username")
    password: SecretStr = Field(description="Starburst password")
    catalog: str = Field(default="bigquery", description="Default catalog (BigQuery for Starburst Galaxy)")
    schema_name: str = Field(default="public", alias="schema", description="Default schema")
    # Timeout for individual HTTP requests to Starburst (not query timeout)
    request_timeout_seconds: int = Field(default=30, description="HTTP request timeout")
    # Resource group routing (ADR-025)
    client_tags: str = Field(
        default="graph-olap-export",
        description="Client tags for Starburst resource group routing",
    )
    source: str = Field(
        default="graph-olap-export-worker",
        description="Source identifier for Starburst",
    )


class GCSConfig(BaseSettings):
    """Google Cloud Storage configuration."""

    model_config = SettingsConfigDict(env_prefix="GCS_")

    project: str = Field(alias="GCP_PROJECT", description="GCP project ID")
    emulator_host: str | None = Field(
        default=None,
        alias="STORAGE_EMULATOR_HOST",
        description="GCS emulator endpoint (for testing)",
    )


class ControlPlaneConfig(BaseSettings):
    """Control Plane API configuration."""

    model_config = SettingsConfigDict(env_prefix="CONTROL_PLANE_")

    url: str = Field(description="Control Plane internal URL")
    timeout_seconds: int = Field(default=30, description="Request timeout")
    max_retries: int = Field(default=5, description="Max retry attempts")
    internal_api_key: SecretStr | None = Field(
        default=None,
        alias="GRAPH_OLAP_INTERNAL_API_KEY",
        description="Internal API key for service-to-service auth",
    )


class Settings(BaseSettings):
    """Application settings aggregating all configurations.

    ADR-025: Database polling architecture - no Pub/Sub.
    Query throttling handled by Starburst resource groups, not client-side.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Core GCP settings
    gcp_project: str = Field(alias="GCP_PROJECT", description="GCP project ID")

    # Worker loop settings (ADR-025)
    poll_interval_seconds: int = Field(
        default=5,
        alias="POLL_INTERVAL_SECONDS",
        description="How often to run main loop when work is found",
    )
    empty_poll_backoff_seconds: int = Field(
        default=10,
        alias="EMPTY_POLL_BACKOFF_SECONDS",
        description="Backoff seconds when no work found",
    )
    claim_limit: int = Field(
        default=10,
        alias="CLAIM_LIMIT",
        description="Max jobs to claim per cycle",
    )
    poll_limit: int = Field(
        default=10,
        alias="POLL_LIMIT",
        description="Max jobs to poll per cycle",
    )

    # Component configs
    starburst: StarburstConfig = Field(default_factory=StarburstConfig)
    gcs: GCSConfig = Field(default_factory=GCSConfig)
    control_plane: ControlPlaneConfig = Field(default_factory=ControlPlaneConfig)

    # Logging
    log_level: str = Field(default="INFO", description="Logging level")
    log_format: str = Field(default="json", description="Log format: json or console")

    # Feature flags
    dry_run: bool = Field(default=False, description="Skip actual exports (for testing)")


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance.

    Returns:
        Singleton Settings instance loaded from environment.
    """
    return Settings()


def clear_settings_cache() -> None:
    """Clear the settings cache (useful for testing)."""
    get_settings.cache_clear()
