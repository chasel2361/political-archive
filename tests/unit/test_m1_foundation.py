from pathlib import Path

import pytest
from pydantic import SecretStr

from political_archive.config import AppSettings, validate_test_database_target
from political_archive.crawl import sanitize_error_summary
from political_archive.db import database_url, session_factory
from political_archive.dedup import canonicalize_url, sha256_hex
from political_archive.storage import (
    ArtifactKind,
    StorageConflictError,
    StorageError,
    StoredArtifact,
    read_artifact,
    store_artifact,
)


def test_url_canonicalization_is_conservative() -> None:
    assert (
        canonicalize_url("HTTPS://Example.COM:443?utm_source=news&b=2&a=1#fragment")
        == "https://example.com/?a=1&b=2"
    )
    assert canonicalize_url("http://Example.com:8080/path?b=2&a=1") == (
        "http://example.com:8080/path?a=1&b=2"
    )
    assert canonicalize_url("https://example.com/?q=utm_source") == (
        "https://example.com/?q=utm_source"
    )
    with pytest.raises(ValueError):
        canonicalize_url("not a URL")
    with pytest.raises(ValueError):
        canonicalize_url("https://example.com:bad/")


def test_sha256_hash_is_stable() -> None:
    assert sha256_hex(b"archive") == (
        "0eb3e36bfb24dcd9bb1d1bece1531216b59539a8fde17ee80224af0653c92aa3"
    )


@pytest.mark.parametrize(
    "kind",
    [ArtifactKind.PDF, ArtifactKind.HTML, ArtifactKind.JSON, ArtifactKind.MARKDOWN],
)
def test_artifact_round_trip_and_idempotency(
    tmp_path: Path, kind: ArtifactKind
) -> None:
    content = b"raw evidence\n" if kind is not ArtifactKind.PDF else b"%PDF-test"
    artifact = store_artifact(tmp_path, kind, content)
    assert artifact.compressed is (kind is not ArtifactKind.PDF)
    assert read_artifact(tmp_path, artifact) == content
    assert store_artifact(tmp_path, kind, content) == artifact


def test_corrupt_artifact_is_rejected(tmp_path: Path) -> None:
    artifact = store_artifact(tmp_path, ArtifactKind.HTML, b"content")
    (tmp_path / artifact.relative_path).write_bytes(b"not zstd")
    with pytest.raises(StorageConflictError):
        store_artifact(tmp_path, ArtifactKind.HTML, b"content")


def test_path_and_symlink_safety(tmp_path: Path) -> None:
    (tmp_path / "source").symlink_to(tmp_path / "outside", target_is_directory=False)
    with pytest.raises(StorageError):
        store_artifact(tmp_path, ArtifactKind.PDF, b"blocked")


@pytest.mark.parametrize(
    "forged_path",
    [Path("/tmp/forged.pdf"), Path("source/../forged.pdf")],
)
def test_forged_artifact_paths_are_rejected(tmp_path: Path, forged_path: Path) -> None:
    forged = StoredArtifact(forged_path, "0" * 64, 1, False)
    with pytest.raises(StorageError):
        read_artifact(tmp_path, forged)


def test_database_url_masks_password() -> None:
    settings = AppSettings(database_password=SecretStr("plain-secret"))
    url = database_url(settings)
    assert "plain-secret" not in str(url)
    assert "plain-secret" not in repr(url)


def test_session_factory_honors_explicit_settings() -> None:
    factory = session_factory(AppSettings(database_name="explicit_test_database"))
    engine = factory.kw["bind"]
    try:
        assert engine.url.database == "explicit_test_database"
    finally:
        engine.dispose()


def test_integration_database_guard() -> None:
    validate_test_database_target("127.0.0.1", "political_archive_test")
    with pytest.raises(ValueError, match="development database"):
        validate_test_database_target("127.0.0.1", "political_archive")
    with pytest.raises(ValueError, match="loopback"):
        validate_test_database_target("db.example", "political_archive_test")
    validate_test_database_target(
        "db.example", "political_archive_test", allow_remote=True
    )


def test_error_summary_redacts_secrets() -> None:
    value = sanitize_error_summary(
        "password=secret token:abc https://user:pass@example.test/path"
    )
    assert "secret" not in value
    assert "abc" not in value
    assert "user:pass" not in value
