"""Typed SQLAlchemy models for the M1 evidence database."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    BIGINT,
    NUMERIC,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Integer,
    PrimaryKeyConstraint,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class ReviewStatus(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class CrawlRunStatus(StrEnum):
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


class DocumentPersonRelation(StrEnum):
    MENTIONED = "mentioned"
    SPEAKER = "speaker"
    PROPOSER = "proposer"
    CO_PROPOSER = "co_proposer"
    COSIGNER = "cosigner"
    COMMENTED_ON = "commented_on"
    FACT_CHECKED = "fact_checked"


class LegislativeItemType(StrEnum):
    BILL = "bill"
    BILL_VERSION = "bill_version"
    ANNUAL_BUDGET = "annual_budget"
    SPECIAL_BUDGET = "special_budget"
    FISCAL_LEGISLATIVE_PROPOSAL = "fiscal_legislative_proposal"
    ALTERNATIVE_SPENDING_PLAN = "alternative_spending_plan"
    BUDGET_CUT = "budget_cut"
    BUDGET_FREEZE = "budget_freeze"
    UNFREEZE = "unfreeze"
    MAIN_RESOLUTION = "main_resolution"
    ATTACHED_RESOLUTION = "attached_resolution"


class LegislativePersonRole(StrEnum):
    PRIMARY_PROPOSER = "primary_proposer"
    CO_PROPOSER = "co_proposer"
    COSIGNER = "cosigner"
    SUPPORTER = "supporter"
    OPPONENT = "opponent"
    PROCEDURE_INITIATOR = "procedure_initiator"


def _values(enum_type: type[StrEnum]) -> str:
    return ", ".join(repr(item.value) for item in enum_type)


UTC_TIMESTAMP = DateTime(timezone=True)


class Base(DeclarativeBase):
    """Declarative metadata; schema changes belong in Alembic migrations."""


class Person(Base):
    __tablename__ = "person"

    id: Mapped[int] = mapped_column(BIGINT, Identity(always=False), primary_key=True)
    canonical_name: Mapped[str] = mapped_column(String(200), nullable=False)
    party: Mapped[str | None] = mapped_column(String(200))
    constituency: Mapped[str | None] = mapped_column(String(200))
    term: Mapped[str | None] = mapped_column(String(200))
    active_from: Mapped[date | None] = mapped_column(Date)
    active_to: Mapped[date | None] = mapped_column(Date)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )


class PersonAlias(Base):
    __tablename__ = "person_alias"
    __table_args__ = (
        UniqueConstraint("person_id", "alias", name="uq_person_alias_person_alias"),
        Index("ix_person_alias_alias", "alias"),
    )

    id: Mapped[int] = mapped_column(BIGINT, Identity(always=False), primary_key=True)
    person_id: Mapped[int] = mapped_column(
        BIGINT, ForeignKey("person.id", ondelete="CASCADE"), nullable=False
    )
    alias: Mapped[str] = mapped_column(String(200), nullable=False)
    alias_type: Mapped[str | None] = mapped_column(String(100))


class Source(Base):
    __tablename__ = "source"
    __table_args__ = (UniqueConstraint("name", name="uq_source_name"),)

    id: Mapped[int] = mapped_column(BIGINT, Identity(always=False), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    source_type: Mapped[str] = mapped_column(String(100), nullable=False)
    base_url: Mapped[str | None] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    last_success_at: Mapped[datetime | None] = mapped_column(UTC_TIMESTAMP)
    cursor_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )


class Document(Base):
    __tablename__ = "document"
    __table_args__ = (
        Index(
            "uq_document_source_external_id",
            "source_id",
            "external_id",
            unique=True,
            postgresql_where=text("external_id IS NOT NULL"),
        ),
        Index("ix_document_source_last_seen", "source_id", "last_seen_at"),
        Index("ix_document_published_at", "published_at"),
        Index("ix_document_current_revision", "current_revision_id"),
        CheckConstraint(
            "external_id IS NULL OR length(external_id) > 0",
            name="ck_document_external_id_nonempty",
        ),
    )

    id: Mapped[int] = mapped_column(BIGINT, Identity(always=False), primary_key=True)
    source_id: Mapped[int] = mapped_column(
        BIGINT, ForeignKey("source.id", ondelete="RESTRICT"), nullable=False
    )
    external_id: Mapped[str | None] = mapped_column(String(300))
    canonical_url: Mapped[str | None] = mapped_column(Text, unique=True)
    document_type: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str | None] = mapped_column(Text)
    author: Mapped[str | None] = mapped_column(Text)
    published_at: Mapped[datetime | None] = mapped_column(UTC_TIMESTAMP)
    first_seen_at: Mapped[datetime] = mapped_column(
        UTC_TIMESTAMP, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        UTC_TIMESTAMP, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    current_revision_id: Mapped[int | None] = mapped_column(
        BIGINT,
        ForeignKey(
            "document_revision.id",
            name="fk_document_current_revision",
            ondelete="SET NULL",
            use_alter=True,
        ),
    )


class DocumentRevision(Base):
    __tablename__ = "document_revision"
    __table_args__ = (
        UniqueConstraint(
            "document_id", "content_hash", name="uq_revision_document_content_hash"
        ),
        Index("ix_revision_document_created", "document_id", "created_at"),
        Index("ix_revision_content_hash", "content_hash"),
        CheckConstraint(
            "content_hash ~ '^[0-9a-f]{64}$'", name="ck_revision_content_hash_sha256"
        ),
        CheckConstraint(
            "normalized_content_hash IS NULL OR normalized_content_hash ~ "
            "'^[0-9a-f]{64}$'",
            name="ck_revision_normalized_hash_sha256",
        ),
        CheckConstraint(
            "review_status IN ('PENDING', 'APPROVED', 'REJECTED')",
            name="ck_revision_review_status",
        ),
    )

    id: Mapped[int] = mapped_column(BIGINT, Identity(always=False), primary_key=True)
    document_id: Mapped[int] = mapped_column(
        BIGINT, ForeignKey("document.id", ondelete="CASCADE"), nullable=False
    )
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    normalized_content_hash: Mapped[str | None] = mapped_column(String(64))
    raw_path: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_path: Mapped[str | None] = mapped_column(Text)
    parsed_text: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    parser_name: Mapped[str | None] = mapped_column(String(200))
    parser_version: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(
        UTC_TIMESTAMP, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    review_status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'PENDING'")
    )


class DocumentPerson(Base):
    __tablename__ = "document_person"
    __table_args__ = (
        PrimaryKeyConstraint("document_id", "person_id", "relation_type"),
        CheckConstraint(
            f"relation_type IN ({_values(DocumentPersonRelation)})",
            name="ck_document_person_relation_type",
        ),
        CheckConstraint(
            "confidence >= 0 AND confidence <= 1", name="ck_document_person_confidence"
        ),
        Index("ix_document_person_person", "person_id"),
    )

    document_id: Mapped[int] = mapped_column(
        BIGINT, ForeignKey("document.id", ondelete="CASCADE")
    )
    person_id: Mapped[int] = mapped_column(
        BIGINT, ForeignKey("person.id", ondelete="CASCADE")
    )
    relation_type: Mapped[str] = mapped_column(String(40))
    confidence: Mapped[Decimal] = mapped_column(NUMERIC(4, 3), nullable=False)


class LegislativeItem(Base):
    __tablename__ = "legislative_item"
    __table_args__ = (
        CheckConstraint(
            f"item_type IN ({_values(LegislativeItemType)})",
            name="ck_legislative_item_type",
        ),
        CheckConstraint(
            "proposed_amount >= 0", name="ck_legislative_item_proposed_amount"
        ),
        CheckConstraint(
            "approved_amount >= 0", name="ck_legislative_item_approved_amount"
        ),
        Index("ix_legislative_item_type_status", "item_type", "status"),
        Index("ix_legislative_item_source_document", "source_document_id"),
        Index(
            "uq_legislative_item_external_id",
            "external_id",
            unique=True,
            postgresql_where=text("external_id IS NOT NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(BIGINT, Identity(always=False), primary_key=True)
    item_type: Mapped[str] = mapped_column(String(60), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    external_id: Mapped[str | None] = mapped_column(String(300))
    origin_type: Mapped[str | None] = mapped_column(String(100))
    fiscal_year: Mapped[int | None] = mapped_column(Integer)
    agency: Mapped[str | None] = mapped_column(String(300))
    program: Mapped[str | None] = mapped_column(Text)
    proposed_amount: Mapped[Decimal | None] = mapped_column(NUMERIC(20, 2))
    approved_amount: Mapped[Decimal | None] = mapped_column(NUMERIC(20, 2))
    status: Mapped[str | None] = mapped_column(String(100))
    parent_item_id: Mapped[int | None] = mapped_column(
        BIGINT, ForeignKey("legislative_item.id", ondelete="SET NULL")
    )
    source_document_id: Mapped[int | None] = mapped_column(
        BIGINT, ForeignKey("document.id", ondelete="SET NULL")
    )
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )


class LegislativePerson(Base):
    __tablename__ = "legislative_person"
    __table_args__ = (
        PrimaryKeyConstraint("legislative_item_id", "person_id", "role"),
        CheckConstraint(
            f"role IN ({_values(LegislativePersonRole)})",
            name="ck_legislative_person_role",
        ),
        Index("ix_legislative_person_person", "person_id"),
    )

    legislative_item_id: Mapped[int] = mapped_column(
        BIGINT, ForeignKey("legislative_item.id", ondelete="CASCADE")
    )
    person_id: Mapped[int] = mapped_column(
        BIGINT, ForeignKey("person.id", ondelete="CASCADE")
    )
    role: Mapped[str] = mapped_column(String(40))


class ProcedureEvent(Base):
    __tablename__ = "procedure_event"
    __table_args__ = (
        CheckConstraint(
            "length(event_type) > 0", name="ck_procedure_event_type_nonempty"
        ),
        Index("ix_procedure_event_item_date", "legislative_item_id", "event_date"),
        Index("ix_procedure_event_type_date", "event_type", "event_date"),
    )

    id: Mapped[int] = mapped_column(BIGINT, Identity(always=False), primary_key=True)
    legislative_item_id: Mapped[int] = mapped_column(
        BIGINT, ForeignKey("legislative_item.id", ondelete="CASCADE"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    event_date: Mapped[date | None] = mapped_column(Date)
    description: Mapped[str | None] = mapped_column(Text)
    result: Mapped[str | None] = mapped_column(Text)
    source_document_id: Mapped[int | None] = mapped_column(
        BIGINT, ForeignKey("document.id", ondelete="SET NULL")
    )
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )


class CrawlRun(Base):
    __tablename__ = "crawl_run"
    __table_args__ = (
        CheckConstraint(
            "status IN ('RUNNING', 'SUCCEEDED', 'PARTIAL', 'FAILED')",
            name="ck_crawl_run_status",
        ),
        CheckConstraint("discovered_count >= 0", name="ck_crawl_run_discovered_count"),
        CheckConstraint("downloaded_count >= 0", name="ck_crawl_run_downloaded_count"),
        CheckConstraint("parsed_count >= 0", name="ck_crawl_run_parsed_count"),
        CheckConstraint("failed_count >= 0", name="ck_crawl_run_failed_count"),
        Index("ix_crawl_run_source_started", "source_id", "started_at"),
        Index("ix_crawl_run_status_started", "status", "started_at"),
    )

    id: Mapped[int] = mapped_column(BIGINT, Identity(always=False), primary_key=True)
    source_id: Mapped[int] = mapped_column(
        BIGINT, ForeignKey("source.id", ondelete="RESTRICT"), nullable=False
    )
    started_at: Mapped[datetime] = mapped_column(
        UTC_TIMESTAMP, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    finished_at: Mapped[datetime | None] = mapped_column(UTC_TIMESTAMP)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'RUNNING'")
    )
    discovered_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    downloaded_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    parsed_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    failed_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    error_summary: Mapped[str | None] = mapped_column(Text)


class ReviewOverride(Base):
    __tablename__ = "review_override"
    __table_args__ = (
        CheckConstraint(
            "previous_status IN ('PENDING', 'APPROVED', 'REJECTED')",
            name="ck_review_override_previous_status",
        ),
        CheckConstraint(
            "new_status IN ('PENDING', 'APPROVED', 'REJECTED')",
            name="ck_review_override_new_status",
        ),
        Index(
            "ix_review_override_revision_created", "document_revision_id", "created_at"
        ),
    )

    id: Mapped[int] = mapped_column(BIGINT, Identity(always=False), primary_key=True)
    document_revision_id: Mapped[int] = mapped_column(
        BIGINT, ForeignKey("document_revision.id", ondelete="RESTRICT"), nullable=False
    )
    previous_status: Mapped[str] = mapped_column(String(20), nullable=False)
    new_status: Mapped[str] = mapped_column(String(20), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    reviewer: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        UTC_TIMESTAMP, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )


__all__ = [
    "Base",
    "CrawlRun",
    "CrawlRunStatus",
    "Document",
    "DocumentPerson",
    "DocumentPersonRelation",
    "DocumentRevision",
    "LegislativeItem",
    "LegislativeItemType",
    "LegislativePerson",
    "LegislativePersonRole",
    "Person",
    "PersonAlias",
    "ProcedureEvent",
    "ReviewOverride",
    "ReviewStatus",
    "Source",
]
