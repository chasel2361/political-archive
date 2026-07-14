from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from political_archive.crawl import (
    CrawlCounter,
    fail_crawl_run,
    finish_crawl_run,
    increment_counter,
    start_crawl_run,
)
from political_archive.dedup import (
    DocumentIdentity,
    find_normalized_revision_candidates,
    find_raw_revision_candidates,
    find_revision_candidate,
    get_or_create_document,
    get_or_create_revision,
    sha256_hex,
)
from political_archive.models import (
    Base,
    DocumentPerson,
    LegislativeItem,
    Person,
    ProcedureEvent,
    ReviewOverride,
    Source,
)


@pytest.mark.integration
def test_migration_has_all_tables_and_by_default_identity(
    integration_session_factory: object,
) -> None:
    factory = integration_session_factory
    session = factory()
    try:
        names = set(inspect(session.bind).get_table_names())  # type: ignore[arg-type]
        assert names >= set(Base.metadata.tables)
        identity_columns = session.execute(
            text(
                "SELECT table_name, column_name, identity_generation "
                "FROM information_schema.columns "
                "WHERE table_schema='public' AND identity_generation IS NOT NULL"
            )
        ).all()
        assert len(identity_columns) == 9
        assert {row.identity_generation for row in identity_columns} == {"BY DEFAULT"}
    finally:
        session.close()


@pytest.mark.integration
def test_constraints_dates_and_transaction_rollback(
    integration_session_factory: object,
) -> None:
    factory = integration_session_factory
    session: Session = factory()
    try:
        source = Source(name="schema-source", source_type="fixture")
        person = Person(canonical_name="Test Person", active_from=date(2026, 1, 1))
        session.add_all([source, person])
        session.commit()
        with pytest.raises(IntegrityError):
            session.add(Source(name="schema-source", source_type="duplicate"))
            session.commit()
        session.rollback()
        with pytest.raises(IntegrityError):
            session.add(
                LegislativeItem(
                    title="bad", item_type="not-an-item", proposed_amount=Decimal("-1")
                )
            )
            session.commit()
        session.rollback()
        with pytest.raises(IntegrityError):
            session.add(
                DocumentPerson(
                    document_id=999999,
                    person_id=person.id,
                    relation_type="invalid",
                    confidence=Decimal("1.1"),
                )
            )
            session.commit()
        session.rollback()
        session.add(
            ProcedureEvent(legislative_item_id=999999, event_type="future_event")
        )
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()
        with session.begin():
            session.add(Person(canonical_name="rolled back"))
            raise RuntimeError("rollback test")
    except RuntimeError:
        pass
    finally:
        session.close()


@pytest.mark.integration
def test_document_revision_dedup_and_hash_candidates(
    integration_session_factory: object,
) -> None:
    session: Session = integration_session_factory()
    try:
        source = Source(name="revision-source", source_type="fixture")
        session.add(source)
        session.flush()
        document = get_or_create_document(
            session,
            DocumentIdentity(source.id, "ext-1", "https://example.test/item#x", "html"),
        )
        raw_one = sha256_hex(b"one")
        normalized = sha256_hex(b"same")
        first, created = get_or_create_revision(
            session, document.id, raw_one, "source/html/one", normalized
        )
        assert created
        same, created = get_or_create_revision(
            session, document.id, raw_one, "source/html/one-again", normalized
        )
        assert not created and same.id == first.id
        second, created = get_or_create_revision(
            session, document.id, sha256_hex(b"two"), "source/html/two", normalized
        )
        assert created and second.id != first.id
        session.flush()
        assert document.current_revision_id == second.id
        assert find_raw_revision_candidates(session, raw_one) == [first]
        assert find_normalized_revision_candidates(session, normalized) == [
            first,
            second,
        ]
        assert find_revision_candidate(session, raw_one, normalized) is first
        session.commit()
    finally:
        session.close()


@pytest.mark.integration
def test_crawl_lifecycle_and_review_audit(integration_session_factory: object) -> None:
    session: Session = integration_session_factory()
    try:
        source = Source(name="crawl-source", source_type="fixture")
        session.add(source)
        session.flush()
        run = start_crawl_run(session, source.id)
        increment_counter(session, run.id, CrawlCounter.DISCOVERED, 2)
        increment_counter(session, run.id, CrawlCounter.DOWNLOADED)
        finish_crawl_run(session, run.id)
        with pytest.raises(LookupError):
            increment_counter(session, run.id, CrawlCounter.PARSED)
        document = get_or_create_document(
            session,
            DocumentIdentity(source.id, "review-1", None, "html"),
        )
        revision, _ = get_or_create_revision(
            session, document.id, sha256_hex(b"review"), "source/html/review"
        )
        session.add_all(
            [
                ReviewOverride(
                    document_revision_id=revision.id,
                    previous_status="PENDING",
                    new_status="APPROVED",
                    reason="checked",
                    reviewer="tester",
                ),
                ReviewOverride(
                    document_revision_id=revision.id,
                    previous_status="APPROVED",
                    new_status="REJECTED",
                    reason="reopened",
                    reviewer="tester",
                ),
            ]
        )
        session.commit()
        assert len(session.scalars(select(ReviewOverride)).all()) == 2
        failed = start_crawl_run(session, source.id)
        fail_crawl_run(session, failed.id, "password=hidden token=secret")
        session.commit()
        assert failed.error_summary == "password=<redacted> token=<redacted>"
    finally:
        session.close()
