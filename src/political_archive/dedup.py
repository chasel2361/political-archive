"""Small deterministic URL and database deduplication helpers."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from political_archive.models import Document, DocumentRevision

_TRACKING_PARAMETERS = frozenset(
    {
        "utm_source",
        "utm_medium",
        "utm_campaign",
        "utm_term",
        "utm_content",
        "gclid",
        "fbclid",
    }
)
_USERINFO_PATTERN = re.compile(r"(?i)(password|passwd|secret|token)\s*[=:]\s*[^\s,;]+")


def sha256_hex(content: bytes) -> str:
    """Return a lowercase SHA-256 hash suitable for the schema constraint."""
    return hashlib.sha256(content).hexdigest()


def canonicalize_url(value: str) -> str:
    """Canonicalize only URL details that are unambiguously presentation noise."""
    parsed = urlsplit(value.strip())
    if not parsed.scheme or not parsed.hostname:
        raise ValueError("URL must include a scheme and host")
    scheme = parsed.scheme.lower()
    hostname = parsed.hostname.lower()
    try:
        port = parsed.port
    except ValueError as error:
        raise ValueError("URL has an invalid port") from error
    default_port = (scheme == "http" and port == 80) or (
        scheme == "https" and port == 443
    )
    host = f"[{hostname}]" if ":" in hostname else hostname
    netloc = host if port is None or default_port else f"{host}:{port}"
    query = sorted(
        (key, item)
        for key, item in parse_qsl(parsed.query, keep_blank_values=True)
        if key.lower() not in _TRACKING_PARAMETERS
    )
    return urlunsplit((scheme, netloc, parsed.path or "/", urlencode(query), ""))


def normalize_text_hash(content: bytes) -> str:
    """Hash normalized bytes; normalization itself belongs to later pipeline work."""
    return sha256_hex(content)


def find_raw_revision_candidates(
    session: Session, content_hash: str
) -> list[DocumentRevision]:
    """Return revisions with an exact raw-byte hash, oldest first."""
    return list(
        session.scalars(
            select(DocumentRevision)
            .where(DocumentRevision.content_hash == content_hash)
            .order_by(DocumentRevision.id)
        )
    )


def find_normalized_revision_candidates(
    session: Session, normalized_content_hash: str
) -> list[DocumentRevision]:
    """Return revisions with an exact normalized-content hash, oldest first."""
    return list(
        session.scalars(
            select(DocumentRevision)
            .where(DocumentRevision.normalized_content_hash == normalized_content_hash)
            .order_by(DocumentRevision.id)
        )
    )


def find_revision_candidate(
    session: Session,
    content_hash: str | None = None,
    normalized_content_hash: str | None = None,
) -> DocumentRevision | None:
    """Find one candidate, preferring raw hash over normalized hash."""
    if content_hash is not None:
        raw = find_raw_revision_candidates(session, content_hash)
        if raw:
            return raw[0]
    if normalized_content_hash is not None:
        normalized = find_normalized_revision_candidates(
            session, normalized_content_hash
        )
        if normalized:
            return normalized[0]
    return None


def find_document(
    session: Session,
    source_id: int,
    external_id: str | None,
    canonical_url: str | None,
) -> Document | None:
    """Find by the documented priority: source external ID, URL, then none."""
    if external_id is not None:
        document = session.scalar(
            select(Document).where(
                Document.source_id == source_id, Document.external_id == external_id
            )
        )
        if document is not None:
            return document
    if canonical_url is not None:
        return session.scalar(
            select(Document).where(Document.canonical_url == canonical_url)
        )
    return None


@dataclass(frozen=True, slots=True)
class DocumentIdentity:
    source_id: int
    external_id: str | None
    canonical_url: str | None
    document_type: str
    title: str | None = None


def get_or_create_document(session: Session, identity: DocumentIdentity) -> Document:
    """Get or insert a document, using savepoints for concurrent unique races."""
    canonical_url = (
        canonicalize_url(identity.canonical_url) if identity.canonical_url else None
    )
    existing = find_document(
        session, identity.source_id, identity.external_id, canonical_url
    )
    if existing is not None:
        return existing
    document = Document(
        source_id=identity.source_id,
        external_id=identity.external_id,
        canonical_url=canonical_url,
        document_type=identity.document_type,
        title=identity.title,
    )
    try:
        with session.begin_nested():
            session.add(document)
            session.flush()
    except IntegrityError:
        existing = find_document(
            session, identity.source_id, identity.external_id, canonical_url
        )
        if existing is None:
            raise
        return existing
    return document


def get_or_create_revision(
    session: Session,
    document_id: int,
    content_hash: str,
    raw_path: str,
    normalized_content_hash: str | None = None,
    normalized_path: str | None = None,
    parsed_text: str | None = None,
    metadata_json: dict[str, object] | None = None,
    parser_name: str | None = None,
    parser_version: str | None = None,
) -> tuple[DocumentRevision, bool]:
    """Persist a raw revision exactly once and update the current pointer."""
    existing = session.scalar(
        select(DocumentRevision).where(
            DocumentRevision.document_id == document_id,
            DocumentRevision.content_hash == content_hash,
        )
    )
    if existing is not None:
        return existing, False
    revision = DocumentRevision(
        document_id=document_id,
        content_hash=content_hash,
        normalized_content_hash=normalized_content_hash,
        raw_path=raw_path,
        normalized_path=normalized_path,
        parsed_text=parsed_text,
        metadata_json=metadata_json or {},
        parser_name=parser_name,
        parser_version=parser_version,
    )
    try:
        with session.begin_nested():
            session.add(revision)
            session.flush()
    except IntegrityError:
        existing = session.scalar(
            select(DocumentRevision).where(
                DocumentRevision.document_id == document_id,
                DocumentRevision.content_hash == content_hash,
            )
        )
        if existing is None:
            raise
        return existing, False
    document = session.get(Document, document_id)
    if document is None:
        raise LookupError(f"document not found: {document_id}")
    document.current_revision_id = revision.id
    return revision, True


__all__ = [
    "DocumentIdentity",
    "canonicalize_url",
    "find_document",
    "find_normalized_revision_candidates",
    "find_raw_revision_candidates",
    "find_revision_candidate",
    "get_or_create_document",
    "get_or_create_revision",
    "normalize_text_hash",
    "sha256_hex",
]
