# Architecture

## Current boundary

M0 是設定、套件、CLI entry point 與本機 PostgreSQL foundation。M1 加入 typed
SQLAlchemy schema、Alembic migration、content-addressed evidence storage、
hash/revision dedup helpers、crawl run tracking 與 review audit。沒有 async
fetcher、真實 adapter、crawler container 或完整 CLI。

## Evidence and database flow

```text
source result
     │
     ▼
atomic content-addressed filesystem write
     │ (failure leaves no partial destination)
     ▼
short per-document DB transaction
     │
     ├── document identity: external ID → canonical URL → hash candidates
     └── immutable document revision/current pointer
```

Storage 不 commit DB。檔案成功但 DB rollback 時可有安全 orphan；這避免為了
避免 orphan 而覆寫或刪除可追溯證據，orphan cleanup 延後到後續 operations
milestone。raw PDF 不壓縮，text/JSON/Markdown 使用 zstd；raw hash 與
normalized hash 分開保存。

## Database boundary

`db.py` 只建立 synchronous SQLAlchemy 2 engine/session factory；import 不連線。
設定的 pool size/timeout 可由 `PA_DATABASE_POOL_SIZE` 與
`PA_DATABASE_POOL_TIMEOUT` 控制，password 使用 `SecretStr` 與 SQLAlchemy
masked URL，不進 repr、log 或錯誤摘要。所有 schema 變更只能透過 Alembic。

## Deferred flow

未來 async source adapters 會使用 bounded concurrency、retry 與 response limits；
PDF/OCR/Marker 等 CPU-heavy 工作移至 executor。第一個 adapter 是 legislature
bills（M3 規劃），目前不代表已連接真實網站或達到 R1。
