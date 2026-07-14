"""Safe, content-addressed evidence storage."""

from __future__ import annotations

import hashlib
import os
import secrets
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

import zstandard

from political_archive.exceptions import PoliticalArchiveError


class StorageError(PoliticalArchiveError):
    """Base error for evidence storage failures."""


class StorageConflictError(StorageError):
    """Raised when a content-addressed destination already contains other data."""


class ArtifactKind(StrEnum):
    PDF = "pdf"
    HTML = "html"
    JSON = "json"
    MARKDOWN = "markdown"


@dataclass(frozen=True, slots=True)
class StoredArtifact:
    """Metadata returned after an artifact has been safely stored."""

    relative_path: Path
    content_hash: str
    size: int
    compressed: bool


def sha256_bytes(content: bytes) -> str:
    """Return the lowercase SHA-256 digest of raw bytes."""
    return hashlib.sha256(content).hexdigest()


def _validate_digest(digest: str) -> None:
    if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
        raise ValueError("content hash must be a lowercase SHA-256 digest")


def _relative_path(kind: ArtifactKind, digest: str) -> Path:
    _validate_digest(digest)
    if kind is ArtifactKind.PDF:
        return Path("source") / "pdf" / f"{digest}.pdf"
    if kind is ArtifactKind.HTML:
        return Path("source") / "html" / f"{digest}.html.zst"
    if kind is ArtifactKind.JSON:
        return Path("source") / "json" / f"{digest}.json.zst"
    return Path("normalized") / "markdown" / f"{digest}.md.zst"


def _safe_destination(root: Path, relative_path: Path) -> Path:
    """Resolve a relative destination while rejecting traversal and symlinks."""
    if relative_path.is_absolute() or ".." in relative_path.parts:
        raise StorageError("artifact path must be relative and cannot contain '..'")
    root = root.resolve()
    current = root
    for part in relative_path.parts[:-1]:
        current = current / part
        if current.is_symlink():
            raise StorageError("artifact path traverses a symlink")
    destination = root / relative_path
    if destination.is_symlink():
        raise StorageError("artifact destination cannot be a symlink")
    if (
        destination.exists()
        and destination.resolve().parent != destination.parent.resolve()
    ):
        raise StorageError("artifact destination escapes storage root")
    return destination


def _encode(kind: ArtifactKind, content: bytes) -> bytes:
    if kind is ArtifactKind.PDF:
        return content
    return zstandard.ZstdCompressor().compress(content)


def _decode(kind: ArtifactKind, content: bytes) -> bytes:
    if kind is ArtifactKind.PDF:
        return content
    return zstandard.ZstdDecompressor().decompress(content)


def _verify_existing(destination: Path, kind: ArtifactKind, content: bytes) -> bool:
    """Verify a concurrent/existing destination without leaking codec errors."""
    try:
        return _decode(kind, destination.read_bytes()) == content
    except (OSError, zstandard.ZstdError) as error:
        raise StorageConflictError("existing artifact cannot be verified") from error


def store_artifact(root: Path, kind: ArtifactKind, content: bytes) -> StoredArtifact:
    """Atomically write one artifact, or verify an existing identical artifact.

    The hash and returned path refer to uncompressed source content.  This
    function never opens a database or commits a database transaction.
    """
    digest = sha256_bytes(content)
    relative_path = _relative_path(kind, digest)
    destination = _safe_destination(root, relative_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.parent.is_symlink():
        raise StorageError("artifact directory cannot be a symlink")
    encoded = _encode(kind, content)
    if destination.exists():
        if not _verify_existing(destination, kind, content):
            raise StorageConflictError("content-addressed artifact hash collision")
        return StoredArtifact(
            relative_path, digest, len(content), kind is not ArtifactKind.PDF
        )

    temporary = destination.with_name(f".{destination.name}.{secrets.token_hex(8)}.tmp")
    try:
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        descriptor = os.open(temporary, flags, 0o644)
        with os.fdopen(descriptor, "wb") as file:
            file.write(encoded)
            file.flush()
            os.fsync(file.fileno())
        # A hard link publishes the complete fsynced temporary inode with
        # O_EXCL semantics: it never clobbers a winner at destination.
        try:
            os.link(temporary, destination)
        except FileExistsError:
            if _verify_existing(destination, kind, content):
                return StoredArtifact(
                    relative_path, digest, len(content), kind is not ArtifactKind.PDF
                )
            raise StorageConflictError(
                "concurrent content-addressed write conflict"
            ) from None
        except OSError as error:
            raise StorageError("cannot publish artifact atomically") from error
        directory_fd = os.open(destination.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except FileExistsError:
        # A concurrent writer won the race.  Verify its content just as for an
        # ordinary idempotent write.
        if destination.exists() and _verify_existing(destination, kind, content):
            return StoredArtifact(
                relative_path, digest, len(content), kind is not ArtifactKind.PDF
            )
        raise StorageConflictError(
            "concurrent content-addressed write conflict"
        ) from None
    finally:
        temporary.unlink(missing_ok=True)
    return StoredArtifact(
        relative_path, digest, len(content), kind is not ArtifactKind.PDF
    )


def read_artifact(root: Path, artifact: StoredArtifact) -> bytes:
    """Read and decompress a previously returned artifact safely."""
    destination = _safe_destination(root, artifact.relative_path)
    if not destination.is_file():
        raise StorageError("artifact does not exist")
    content = _decode(
        ArtifactKind.PDF if not artifact.compressed else ArtifactKind.MARKDOWN,
        destination.read_bytes(),
    )
    if sha256_bytes(content) != artifact.content_hash:
        raise StorageConflictError("stored artifact hash does not match metadata")
    return content


__all__ = [
    "ArtifactKind",
    "StorageConflictError",
    "StorageError",
    "StoredArtifact",
    "read_artifact",
    "sha256_bytes",
    "store_artifact",
]
