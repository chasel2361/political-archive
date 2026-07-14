"""SQLAlchemy database setup.

This module only constructs SQLAlchemy objects.  Connecting to PostgreSQL is
left to the caller (normally :func:`session_scope`), which keeps imports safe
for commands and unit tests that do not have a database available.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Final

from sqlalchemy import Engine, create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session, sessionmaker

from political_archive.config import AppSettings, load_settings


def database_url(settings: AppSettings | None = None) -> URL:
    """Build a PostgreSQL URL without interpolating or logging its password."""
    config = settings or load_settings()
    return URL.create(
        "postgresql+psycopg",
        username=config.database_user,
        password=config.database_password.get_secret_value(),
        host=config.database_host,
        port=config.database_port,
        database=config.database_name,
    )


def create_db_engine(settings: AppSettings | None = None) -> Engine:
    """Construct a synchronous SQLAlchemy 2 engine; this does not connect."""
    config = settings or load_settings()
    return create_engine(
        database_url(config),
        future=True,
        pool_pre_ping=True,
        pool_size=config.database_pool_size,
        pool_timeout=config.database_pool_timeout,
    )


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Create the typed session factory for an engine."""
    return sessionmaker(bind=engine, class_=Session, expire_on_commit=False)


_DEFAULT_ENGINE: Engine | None = None
_DEFAULT_FACTORY: sessionmaker[Session] | None = None


def session_factory(settings: AppSettings | None = None) -> sessionmaker[Session]:
    """Return a lazily constructed process-local session factory."""
    global _DEFAULT_ENGINE, _DEFAULT_FACTORY
    if settings is not None:
        return make_session_factory(create_db_engine(settings))
    if _DEFAULT_FACTORY is None:
        _DEFAULT_ENGINE = create_db_engine()
        _DEFAULT_FACTORY = make_session_factory(_DEFAULT_ENGINE)
    return _DEFAULT_FACTORY


@contextmanager
def session_scope(
    settings: AppSettings | None = None,
) -> Iterator[Session]:
    """Yield one transaction, committing on success and rolling back on error."""
    session = session_factory(settings)()
    try:
        with session.begin():
            yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


__all__: Final = [
    "create_db_engine",
    "database_url",
    "make_session_factory",
    "session_factory",
    "session_scope",
]
