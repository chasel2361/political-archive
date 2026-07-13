from pathlib import Path

import pytest

from political_archive.config import load_people, load_project_config, load_sources
from political_archive.exceptions import ConfigurationError

PROJECT_ROOT = Path(__file__).parents[2]


def test_example_configuration_loads() -> None:
    config = load_project_config(PROJECT_ROOT / "config")

    assert config.people.people[0].canonical_name == "範例人物"
    assert config.sources.sources["legislature"].adapter == "bills"
    assert not config.sources.sources["cna"].enabled


def test_people_configuration_rejects_duplicate_ids(tmp_path: Path) -> None:
    path = tmp_path / "people.yml"
    path.write_text(
        "people:\n"
        "  - id: duplicate\n    canonical_name: One\n"
        "  - id: duplicate\n    canonical_name: Two\n",
        encoding="utf-8",
    )

    with pytest.raises(ConfigurationError, match="ids must be unique"):
        load_people(path)


def test_sources_configuration_rejects_invalid_concurrency(tmp_path: Path) -> None:
    path = tmp_path / "sources.yml"
    path.write_text(
        "sources:\n"
        "  example:\n    enabled: false\n    adapter: example\n    concurrency: 0\n",
        encoding="utf-8",
    )

    with pytest.raises(ConfigurationError, match="greater than or equal to 1"):
        load_sources(path)


def test_sources_configuration_allows_future_enabled_source(tmp_path: Path) -> None:
    path = tmp_path / "sources.yml"
    path.write_text(
        "sources:\n"
        "  legislature:\n    enabled: true\n    adapter: bills\n"
        "  future-source:\n    enabled: true\n    adapter: future\n",
        encoding="utf-8",
    )

    sources = load_sources(path)

    assert sources.sources["future-source"].enabled
