# Political Archive Crawler

Political Archive Crawler 是以 PostgreSQL 保存可追溯政治公開資料的 Python 專案。

## M0 已完成

本 milestone 只建立可驗證的開發基礎：

- Python 3.12、`uv` package 與 `political-archive --help` CLI
- Pydantic 驗證的 `config/people.yml`、`config/sources.yml` 與本機環境設定
- PostgreSQL 16 的 loopback-only Docker Compose 開發服務
- Ruff、mypy、pytest、pytest-asyncio 設定與 smoke/config tests
- M3 預先選定的第一個資料來源垂直切片：立法院議案／法案（`legislature`，`bills` adapter）

目前**尚未**實作正式 crawler、任何真實來源 adapter、SQLAlchemy models、Alembic schema/migration、document pipeline 或資料寫入流程；CLI 不提供會誤稱這些功能已完成的假命令。

## 本機 PostgreSQL

```bash
cp .env.example .env
docker compose up -d db
docker compose ps
```

資料庫只綁定 `127.0.0.1`。`.env` 僅供本機使用，請勿提交；正式環境必須改用安全 secret 管理。

## 開發指令

```bash
uv sync
uv run political-archive --help
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest
docker compose config
```

可選的 `marker-pdf` 只在 `pdf-full` extra 中，預設 `uv sync` 不會安裝：

```bash
uv sync --extra pdf-full
```

專案規格見 [`PROJECT_spec.md`](PROJECT_spec.md)；里程碑與 R1 gate 見
[`docs/ROADMAP.md`](docs/ROADMAP.md)，架構邊界見
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)。
