"""Validated application and YAML configuration for the M0 foundation."""

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from political_archive.exceptions import ConfigurationError


class PersonConfig(BaseModel):
    """A tracked person entry from ``people.yml``."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    canonical_name: str = Field(min_length=1)
    aliases: list[str] = Field(default_factory=list)
    enabled: bool = True


class PeopleConfig(BaseModel):
    """The top-level people configuration."""

    model_config = ConfigDict(extra="forbid")

    people: list[PersonConfig]

    @field_validator("people")
    @classmethod
    def require_unique_ids(cls, people: list[PersonConfig]) -> list[PersonConfig]:
        """Reject duplicate person identifiers."""
        ids = [person.id for person in people]
        if len(ids) != len(set(ids)):
            raise ValueError("person ids must be unique")
        return people


class SourceConfig(BaseModel):
    """Runtime limits and enablement for a configured source."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    adapter: str = Field(min_length=1)
    concurrency: int = Field(default=2, ge=1)
    requests_per_second: float = Field(default=1.0, gt=0)


class SourcesConfig(BaseModel):
    """The top-level source configuration."""

    model_config = ConfigDict(extra="forbid")

    sources: dict[str, SourceConfig]


class AppSettings(BaseSettings):
    """Environment-backed settings safe for local development."""

    model_config = SettingsConfigDict(
        env_prefix="PA_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_host: str = "127.0.0.1"
    database_port: int = Field(default=5432, ge=1, le=65535)
    database_name: str = "political_archive"
    database_user: str = "political_archive"
    database_password: SecretStr = SecretStr("dev-only-change-me")


class ProjectConfig(BaseModel):
    """Validated project configuration loaded from the two YAML files."""

    people: PeopleConfig
    sources: SourcesConfig
    settings: AppSettings


def _load_yaml(path: Path) -> dict[str, Any]:
    """Load one YAML mapping without allowing unsafe YAML constructors."""
    try:
        with path.open(encoding="utf-8") as file:
            value = yaml.safe_load(file)
    except FileNotFoundError as error:
        raise ConfigurationError(f"configuration file not found: {path}") from error
    except yaml.YAMLError as error:
        raise ConfigurationError(f"invalid YAML in {path}: {error}") from error
    if not isinstance(value, dict):
        raise ConfigurationError(f"configuration must be a YAML mapping: {path}")
    return value


def load_people(path: Path = Path("config/people.yml")) -> PeopleConfig:
    """Load and validate the tracked people configuration."""
    try:
        return PeopleConfig.model_validate(_load_yaml(path))
    except ConfigurationError:
        raise
    except ValueError as error:
        message = f"invalid people configuration in {path}: {error}"
        raise ConfigurationError(message) from error


def load_sources(path: Path = Path("config/sources.yml")) -> SourcesConfig:
    """Load and validate source configuration."""
    try:
        return SourcesConfig.model_validate(_load_yaml(path))
    except ConfigurationError:
        raise
    except ValueError as error:
        message = f"invalid source configuration in {path}: {error}"
        raise ConfigurationError(message) from error


def load_settings() -> AppSettings:
    """Load and validate environment-backed application settings."""
    return AppSettings()


def load_project_config(config_dir: Path = Path("config")) -> ProjectConfig:
    """Load both YAML files and environment settings for the project."""
    return ProjectConfig(
        people=load_people(config_dir / "people.yml"),
        sources=load_sources(config_dir / "sources.yml"),
        settings=load_settings(),
    )
