# Development Guide

## Prerequisites

- Python 3.12
- `uv`
- Docker Engine 與 Docker Compose（只在要啟動本機 PostgreSQL 時需要）

不要手動建立或管理 `.venv`；由 `uv` 管理環境。

## Initial setup

```bash
cp .env.example .env
uv sync
uv run political-archive --help
```

`config/people.yml` 使用範例人物，不包含真實個資；`config/sources.yml` 啟用 legislature 的 `bills` 設定，其餘目前列出的來源停用。設定檔由 Pydantic 驗證，YAML 使用 `safe_load`，不執行 YAML 物件建構器。

## Database

```bash
docker compose config
docker compose up -d db
docker compose ps
```

Compose 目前只有 PostgreSQL 16 `db` service、healthcheck 與 named volume，且 PostgreSQL 只暴露在 loopback。M0 尚未建立 SQLAlchemy models 或 Alembic migrations，因此不要執行 schema upgrade；資料庫 schema 會在後續 milestone 實作。

## Quality checks

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest
```

正常測試不連線 live website，也不要求資料庫。需要真實來源的契約測試未在 M0 實作；未來應使用 `@pytest.mark.live` 並以 `pytest -m live` 明確 opt-in。
