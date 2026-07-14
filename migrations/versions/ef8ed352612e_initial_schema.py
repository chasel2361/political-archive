"""initial schema

Revision ID: ef8ed352612e
Revises:
Create Date: 2026-07-15 00:30:56.550809
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "ef8ed352612e"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "person",
        sa.Column("id", sa.BIGINT(), sa.Identity(always=False), nullable=False),
        sa.Column("canonical_name", sa.String(length=200), nullable=False),
        sa.Column("party", sa.String(length=200), nullable=True),
        sa.Column("constituency", sa.String(length=200), nullable=True),
        sa.Column("term", sa.String(length=200), nullable=True),
        sa.Column("active_from", sa.Date(), nullable=True),
        sa.Column("active_to", sa.Date(), nullable=True),
        sa.Column(
            "metadata_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "source",
        sa.Column("id", sa.BIGINT(), sa.Identity(always=False), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("source_type", sa.String(length=100), nullable=False),
        sa.Column("base_url", sa.Text(), nullable=True),
        sa.Column(
            "enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False
        ),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "cursor_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uq_source_name"),
    )
    op.create_table(
        "crawl_run",
        sa.Column("id", sa.BIGINT(), sa.Identity(always=False), nullable=False),
        sa.Column("source_id", sa.BIGINT(), nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default=sa.text("'RUNNING'"),
            nullable=False,
        ),
        sa.Column(
            "discovered_count",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "downloaded_count",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "parsed_count", sa.Integer(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column(
            "failed_count", sa.Integer(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "status IN ('RUNNING', 'SUCCEEDED', 'PARTIAL', 'FAILED')",
            name="ck_crawl_run_status",
        ),
        sa.CheckConstraint(
            "discovered_count >= 0", name="ck_crawl_run_discovered_count"
        ),
        sa.CheckConstraint(
            "downloaded_count >= 0", name="ck_crawl_run_downloaded_count"
        ),
        sa.CheckConstraint("failed_count >= 0", name="ck_crawl_run_failed_count"),
        sa.CheckConstraint("parsed_count >= 0", name="ck_crawl_run_parsed_count"),
        sa.ForeignKeyConstraint(["source_id"], ["source.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_crawl_run_source_started",
        "crawl_run",
        ["source_id", "started_at"],
        unique=False,
    )
    op.create_index(
        "ix_crawl_run_status_started",
        "crawl_run",
        ["status", "started_at"],
        unique=False,
    )
    op.create_table(
        "document",
        sa.Column("id", sa.BIGINT(), sa.Identity(always=False), nullable=False),
        sa.Column("source_id", sa.BIGINT(), nullable=False),
        sa.Column("external_id", sa.String(length=300), nullable=True),
        sa.Column("canonical_url", sa.Text(), nullable=True),
        sa.Column("document_type", sa.String(length=100), nullable=False),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("author", sa.Text(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "first_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("current_revision_id", sa.BIGINT(), nullable=True),
        sa.CheckConstraint(
            "external_id IS NULL OR length(external_id) > 0",
            name="ck_document_external_id_nonempty",
        ),
        sa.ForeignKeyConstraint(["source_id"], ["source.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("canonical_url"),
    )
    op.create_index(
        "ix_document_current_revision",
        "document",
        ["current_revision_id"],
        unique=False,
    )
    op.create_index(
        "ix_document_published_at", "document", ["published_at"], unique=False
    )
    op.create_index(
        "ix_document_source_last_seen",
        "document",
        ["source_id", "last_seen_at"],
        unique=False,
    )
    op.create_index(
        "uq_document_source_external_id",
        "document",
        ["source_id", "external_id"],
        unique=True,
        postgresql_where=sa.text("external_id IS NOT NULL"),
    )
    op.create_table(
        "person_alias",
        sa.Column("id", sa.BIGINT(), sa.Identity(always=False), nullable=False),
        sa.Column("person_id", sa.BIGINT(), nullable=False),
        sa.Column("alias", sa.String(length=200), nullable=False),
        sa.Column("alias_type", sa.String(length=100), nullable=True),
        sa.ForeignKeyConstraint(["person_id"], ["person.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("person_id", "alias", name="uq_person_alias_person_alias"),
    )
    op.create_index("ix_person_alias_alias", "person_alias", ["alias"], unique=False)
    op.create_table(
        "document_person",
        sa.Column("document_id", sa.BIGINT(), nullable=False),
        sa.Column("person_id", sa.BIGINT(), nullable=False),
        sa.Column("relation_type", sa.String(length=40), nullable=False),
        sa.Column("confidence", sa.NUMERIC(precision=4, scale=3), nullable=False),
        sa.CheckConstraint(
            "relation_type IN ('mentioned', 'speaker', 'proposer', 'co_proposer', "
            "'cosigner', 'commented_on', 'fact_checked')",
            name="ck_document_person_relation_type",
        ),
        sa.CheckConstraint(
            "confidence >= 0 AND confidence <= 1", name="ck_document_person_confidence"
        ),
        sa.ForeignKeyConstraint(["document_id"], ["document.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["person_id"], ["person.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("document_id", "person_id", "relation_type"),
    )
    op.create_index(
        "ix_document_person_person", "document_person", ["person_id"], unique=False
    )
    op.create_table(
        "document_revision",
        sa.Column("id", sa.BIGINT(), sa.Identity(always=False), nullable=False),
        sa.Column("document_id", sa.BIGINT(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("normalized_content_hash", sa.String(length=64), nullable=True),
        sa.Column("raw_path", sa.Text(), nullable=False),
        sa.Column("normalized_path", sa.Text(), nullable=True),
        sa.Column("parsed_text", sa.Text(), nullable=True),
        sa.Column(
            "metadata_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("parser_name", sa.String(length=200), nullable=True),
        sa.Column("parser_version", sa.String(length=100), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "review_status",
            sa.String(length=20),
            server_default=sa.text("'PENDING'"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "content_hash ~ '^[0-9a-f]{64}$'", name="ck_revision_content_hash_sha256"
        ),
        sa.CheckConstraint(
            "normalized_content_hash IS NULL OR normalized_content_hash ~ "
            "'^[0-9a-f]{64}$'",
            name="ck_revision_normalized_hash_sha256",
        ),
        sa.CheckConstraint(
            "review_status IN ('PENDING', 'APPROVED', 'REJECTED')",
            name="ck_revision_review_status",
        ),
        sa.ForeignKeyConstraint(["document_id"], ["document.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "document_id", "content_hash", name="uq_revision_document_content_hash"
        ),
    )
    op.create_index(
        "ix_revision_content_hash", "document_revision", ["content_hash"], unique=False
    )
    op.create_index(
        "ix_revision_document_created",
        "document_revision",
        ["document_id", "created_at"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_document_current_revision",
        "document",
        "document_revision",
        ["current_revision_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_table(
        "legislative_item",
        sa.Column("id", sa.BIGINT(), sa.Identity(always=False), nullable=False),
        sa.Column("item_type", sa.String(length=60), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("external_id", sa.String(length=300), nullable=True),
        sa.Column("origin_type", sa.String(length=100), nullable=True),
        sa.Column("fiscal_year", sa.Integer(), nullable=True),
        sa.Column("agency", sa.String(length=300), nullable=True),
        sa.Column("program", sa.Text(), nullable=True),
        sa.Column("proposed_amount", sa.NUMERIC(precision=20, scale=2), nullable=True),
        sa.Column("approved_amount", sa.NUMERIC(precision=20, scale=2), nullable=True),
        sa.Column("status", sa.String(length=100), nullable=True),
        sa.Column("parent_item_id", sa.BIGINT(), nullable=True),
        sa.Column("source_document_id", sa.BIGINT(), nullable=True),
        sa.Column(
            "metadata_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "item_type IN ('bill', 'bill_version', 'annual_budget', 'special_budget', "
            "'fiscal_legislative_proposal', 'alternative_spending_plan', 'budget_cut', "
            "'budget_freeze', 'unfreeze', 'main_resolution', 'attached_resolution')",
            name="ck_legislative_item_type",
        ),
        sa.CheckConstraint(
            "approved_amount >= 0", name="ck_legislative_item_approved_amount"
        ),
        sa.CheckConstraint(
            "proposed_amount >= 0", name="ck_legislative_item_proposed_amount"
        ),
        sa.ForeignKeyConstraint(
            ["parent_item_id"], ["legislative_item.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["source_document_id"], ["document.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_legislative_item_source_document",
        "legislative_item",
        ["source_document_id"],
        unique=False,
    )
    op.create_index(
        "ix_legislative_item_type_status",
        "legislative_item",
        ["item_type", "status"],
        unique=False,
    )
    op.create_index(
        "uq_legislative_item_external_id",
        "legislative_item",
        ["external_id"],
        unique=True,
        postgresql_where=sa.text("external_id IS NOT NULL"),
    )
    op.create_table(
        "legislative_person",
        sa.Column("legislative_item_id", sa.BIGINT(), nullable=False),
        sa.Column("person_id", sa.BIGINT(), nullable=False),
        sa.Column("role", sa.String(length=40), nullable=False),
        sa.CheckConstraint(
            "role IN ('primary_proposer', 'co_proposer', 'cosigner', 'supporter', "
            "'opponent', 'procedure_initiator')",
            name="ck_legislative_person_role",
        ),
        sa.ForeignKeyConstraint(
            ["legislative_item_id"], ["legislative_item.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["person_id"], ["person.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("legislative_item_id", "person_id", "role"),
    )
    op.create_index(
        "ix_legislative_person_person",
        "legislative_person",
        ["person_id"],
        unique=False,
    )
    op.create_table(
        "procedure_event",
        sa.Column("id", sa.BIGINT(), sa.Identity(always=False), nullable=False),
        sa.Column("legislative_item_id", sa.BIGINT(), nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("event_date", sa.Date(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("result", sa.Text(), nullable=True),
        sa.Column("source_document_id", sa.BIGINT(), nullable=True),
        sa.Column(
            "metadata_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "length(event_type) > 0", name="ck_procedure_event_type_nonempty"
        ),
        sa.ForeignKeyConstraint(
            ["legislative_item_id"], ["legislative_item.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["source_document_id"], ["document.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_procedure_event_item_date",
        "procedure_event",
        ["legislative_item_id", "event_date"],
        unique=False,
    )
    op.create_index(
        "ix_procedure_event_type_date",
        "procedure_event",
        ["event_type", "event_date"],
        unique=False,
    )
    op.create_table(
        "review_override",
        sa.Column("id", sa.BIGINT(), sa.Identity(always=False), nullable=False),
        sa.Column("document_revision_id", sa.BIGINT(), nullable=False),
        sa.Column("previous_status", sa.String(length=20), nullable=False),
        sa.Column("new_status", sa.String(length=20), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("reviewer", sa.String(length=200), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "metadata_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "new_status IN ('PENDING', 'APPROVED', 'REJECTED')",
            name="ck_review_override_new_status",
        ),
        sa.CheckConstraint(
            "previous_status IN ('PENDING', 'APPROVED', 'REJECTED')",
            name="ck_review_override_previous_status",
        ),
        sa.ForeignKeyConstraint(
            ["document_revision_id"], ["document_revision.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_review_override_revision_created",
        "review_override",
        ["document_revision_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_review_override_revision_created", table_name="review_override")
    op.drop_table("review_override")
    op.drop_index("ix_procedure_event_type_date", table_name="procedure_event")
    op.drop_index("ix_procedure_event_item_date", table_name="procedure_event")
    op.drop_table("procedure_event")
    op.drop_index("ix_legislative_person_person", table_name="legislative_person")
    op.drop_table("legislative_person")
    op.drop_index(
        "uq_legislative_item_external_id",
        table_name="legislative_item",
        postgresql_where=sa.text("external_id IS NOT NULL"),
    )
    op.drop_index("ix_legislative_item_type_status", table_name="legislative_item")
    op.drop_index("ix_legislative_item_source_document", table_name="legislative_item")
    op.drop_table("legislative_item")
    op.drop_index("ix_revision_document_created", table_name="document_revision")
    op.drop_index("ix_revision_content_hash", table_name="document_revision")
    op.drop_constraint("fk_document_current_revision", "document", type_="foreignkey")
    op.drop_table("document_revision")
    op.drop_index("ix_document_person_person", table_name="document_person")
    op.drop_table("document_person")
    op.drop_index("ix_person_alias_alias", table_name="person_alias")
    op.drop_table("person_alias")
    op.drop_index(
        "uq_document_source_external_id",
        table_name="document",
        postgresql_where=sa.text("external_id IS NOT NULL"),
    )
    op.drop_index("ix_document_source_last_seen", table_name="document")
    op.drop_index("ix_document_published_at", table_name="document")
    op.drop_index("ix_document_current_revision", table_name="document")
    op.drop_table("document")
    op.drop_index("ix_crawl_run_status_started", table_name="crawl_run")
    op.drop_index("ix_crawl_run_source_started", table_name="crawl_run")
    op.drop_table("crawl_run")
    op.drop_table("source")
    op.drop_table("person")
