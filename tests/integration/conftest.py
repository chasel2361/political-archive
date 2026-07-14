import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session, sessionmaker

from political_archive.config import AppSettings, validate_test_database_target

ROOT = Path(__file__).parents[2]
TEST_DATABASE = "political_archive_test"
ALLOW_REMOTE_ENV = "PA_ALLOW_REMOTE_TEST_DATABASE"


def validate_integration_target(settings: AppSettings) -> None:
    """Guard the fixed test database against accidental remote/prod use."""
    validate_test_database_target(
        settings.database_host,
        TEST_DATABASE,
        allow_remote=os.environ.get(ALLOW_REMOTE_ENV, "").lower() == "true",
    )


@pytest.fixture(scope="session")
def integration_session_factory() -> Iterator[sessionmaker[Session]]:
    settings = AppSettings()
    validate_integration_target(settings)
    maintenance_url = URL.create(
        "postgresql+psycopg",
        username=settings.database_user,
        password=settings.database_password.get_secret_value(),
        host=settings.database_host,
        port=settings.database_port,
        database="postgres",
    )
    maintenance = create_engine(maintenance_url, isolation_level="AUTOCOMMIT")
    with maintenance.connect() as connection:
        present = connection.scalar(
            text("SELECT 1 FROM pg_database WHERE datname = :name"),
            {"name": TEST_DATABASE},
        )
        if present is None:
            connection.exec_driver_sql(f'CREATE DATABASE "{TEST_DATABASE}"')
    maintenance.dispose()

    previous = os.environ.get("PA_DATABASE_NAME")
    os.environ["PA_DATABASE_NAME"] = TEST_DATABASE
    try:
        alembic_config = Config(str(ROOT / "alembic.ini"))
        command.downgrade(alembic_config, "base")
        command.upgrade(alembic_config, "head")
        command.downgrade(alembic_config, "base")
        command.upgrade(alembic_config, "head")
        test_settings = AppSettings()
        engine = create_engine(
            URL.create(
                "postgresql+psycopg",
                username=test_settings.database_user,
                password=test_settings.database_password.get_secret_value(),
                host=test_settings.database_host,
                port=test_settings.database_port,
                database=TEST_DATABASE,
            ),
            pool_pre_ping=True,
        )
        factory = sessionmaker(engine, expire_on_commit=False)
        yield factory
        engine.dispose()
        command.downgrade(alembic_config, "base")
    finally:
        if previous is None:
            os.environ.pop("PA_DATABASE_NAME", None)
        else:
            os.environ["PA_DATABASE_NAME"] = previous
