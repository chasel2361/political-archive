# Development Guide

## Prerequisites and setup

- Python 3.12
- `uv`
- Docker Engine/Compose（需要本機 PostgreSQL 時）

```bash
cp .env.example .env
uv sync --frozen
uv run political-archive --help
```

不要手動管理 `.venv`。`.env` 只放本機設定，不要提交 secrets。

## PostgreSQL and migrations

```bash
docker compose up -d db
docker compose ps
docker compose exec -T db pg_isready -U political_archive -d political_archive
uv run alembic upgrade head
```

查看目前 migration：

```bash
uv run alembic current
```

Migration 是唯一 schema 寫入來源；程式不呼叫 `create_all`。M1 integration
fixture 會以同一個 Compose PostgreSQL server 建立固定的
`political_archive_test` database，先確認名稱、再執行 upgrade → downgrade →
upgrade，預設只接受 `127.0.0.1`、`localhost` 或 `::1`，永遠不會 target 或
drop dev `political_archive`。測試完成後只 downgrade 該 test database。CI 若
明確需要 remote server，必須 opt-in `PA_ALLOW_REMOTE_TEST_DATABASE=true`；這
會允許在 remote server 上操作固定的 test database，應視為有風險的例外。
不要在保存開發資料的 database 上執行 `downgrade base` 來做 round-trip 測試。

## Quality checks

```bash
uv run pytest tests/unit
uv run pytest tests/integration
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy src
```

Unit tests 不需要 DB；integration marker 為 `integration`，live website tests
仍需明確使用 `-m live`。

## M1 transaction boundary

每份 document 先將 raw/normalized artifact 以 content-addressed atomic write
落盤，再在短 DB transaction 中寫入 document/revision。DB rollback 可能留下
orphan artifact，這是刻意的安全取捨；cleanup/backup 尚未屬於 M1。
