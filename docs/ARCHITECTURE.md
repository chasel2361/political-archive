# Architecture

## Current M0 boundary

M0 是設定、套件、CLI 入口與本機 PostgreSQL 開發環境的 foundation。資料庫 container 可啟動，但目前沒有 application schema、migration、ORM model 或資料存取層。CLI 只有 help/version，避免把尚未存在的 crawler 行為偽裝成可用命令。

## Planned flow

```text
scheduled/manual CLI
        │
        ▼
async source adapters ──► source evidence ──► document pipeline
        │                                      │
        └──────────────────────────────────────┴──► PostgreSQL
```

網路抓取預計使用 `httpx.AsyncClient`，並以 bounded concurrency、retry、ETag/Last-Modified 與內容大小限制保護來源。CPU-heavy 的 PDF/Marker/OCR 工作應移到 thread/process executor。原始證據與 normalized Markdown 將以 hash 和 parser metadata 追蹤，避免覆寫 revision。

## First vertical slice

第一個實際 adapter 是 **legislature bills**：立法院議案／法案。這是規劃中的 M3 垂直切片，不代表目前已連接或抓取真實網站。它完成後才會宣稱具備 discover、fetch、parse、normalize、deduplicate 與 database recording 的端到端能力。

## Deliberately deferred

SQLAlchemy data models、Alembic schema/migration、source adapters、document parsing/normalization、person matching、storage pipeline、crawl tracking、exports 與 backup/cleanup scripts 均留待 roadmap 指定 milestone。Web frontend、FastAPI、Redis、Celery、OpenSearch、pgvector、LLM service 及 IVOD video download 不在目前第一階段範圍。
