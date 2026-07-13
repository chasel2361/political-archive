# Roadmap

這份 roadmap 區分目前完成的 foundation 與未來的資料處理能力。只有 M0
已完成；M1–M7 均尚未實作，也不應在文件或 CLI 中被誤稱為已完成。

## M0 — Foundation（已完成）

**依賴：** 無。

**內容：** uv/Python 3.12 package、Pydantic YAML/env 設定、Typer
help/version、Ruff/mypy/pytest 基礎、PostgreSQL 16 loopback-only Compose
service。預設設定選定 legislature 的 `bills` 作為第一個 adapter，其他目前列出的來源停用；這是目前配置，不是永久 schema 限制。

**驗收：** `uv sync`、CLI help、lint/format/type check/tests 與
`docker compose config` 通過；DB 有 healthcheck 與 named volume。未建立
schema、crawler 或 adapter。

## M1 — PostgreSQL schema and evidence foundation（未來）

**依賴：** M0。

**內容：** 以 SQLAlchemy 2 建立規格所列 PostgreSQL schema，加入 Alembic
initial migration；建立 source evidence storage、revision/hash/dedup、
`crawl_run` tracking 與必要的安全檔案寫入邊界。

**驗收：** clean PostgreSQL 可執行 `alembic upgrade head`；schema 僅由
migration 管理；原始證據與 normalized revision 不被覆寫；content hash
變更才建立新 revision；crawl run 與 database integration tests 通過。

## M2 — Shared asynchronous HTTP fetcher（未來）

**依賴：** M1。

**內容：** 建立共用 `httpx.AsyncClient` fetcher，支援 global concurrency 5、
per-domain concurrency 2、rate limiting、3 次 exponential backoff retry、
`Retry-After`、ETag、Last-Modified、content-type validation 與 response size
limits。CPU-heavy 工作不得阻塞 event loop。

**驗收：** deterministic HTTP fixtures/mock tests 驗證上述限制、retry/backoff
與 cache headers；逾時、非預期型別、超大回應與 HTTP failure 產生可診斷錯誤，
且正常測試不連線 live website。

## M3 — Legislature bills end-to-end vertical slice（未來）

**依賴：** M1、M2。

**內容：** 實作第一個正式來源 adapter：**立法院議案／法案（legislature
bills）**。串接 discover、fetch、raw evidence、基本 parse/normalization、
person association、legislative extraction、deduplication 與 crawl status。

**驗收：** 受控 fixtures 與明確 opt-in live contract test 能完成至少一筆
公開 bills record 的 discover → fetch → store → parse → normalize →
deduplicate → database insert → crawl status；保留 raw source 與 normalized
Markdown，不下載 IVOD 影片。

## M4 — CLI, Docker and operations（未來）

**依賴：** M1、M2、M3。

**內容：** 提供 crawler one-shot container 與可手動執行的 CLI，至少支援
`crawl` filters（source/person/date）、`fetch-url`、`status`、`db-upgrade`、
`cleanup-temp --approved-only --dry-run`；加入 backup/restore、structured
logging、overlap window 與排程執行文件。

**驗收：** CLI failure 回傳 non-zero；手動 crawl 與 Docker one-shot 可重現；
cleanup 僅刪除符合 approval、normalized/source/hash/transaction 條件的暫存
檔；backup/restore drill 成功；log 不包含 password/API key。

## M5 — R1 acceptance and hardening（未來）

**依賴：** M1、M2、M3、M4。

**內容：** 針對第一可用版本完成 regression、integration、fixture 與必要
live contract hardening。R1 只驗證一個已完成的來源，不要求先實作全部 adapters。

**R1 gate 驗收：** 逐條滿足規格第 21 節：

1. `uv sync` 建立可用環境。
2. PostgreSQL 透過 Docker Compose 啟動。
3. Alembic migration 成功。
4. 一個來源 adapter 能取得 real record。
5. 原始來源內容被保存。
6. normalized Markdown 以 `.md.zst` 保存。
7. duplicate documents 不會重複插入。
8. tracked people 與 documents 關聯。
9. crawl results 被記錄。
10. manual CLI 可執行。
11. Docker one-shot execution 可執行。
12. tests 通過。
13. temporary files 可透過 cleanup `--dry-run` 安全檢查。
14. database backup 與 restore scripts 存在且可驗證。

M0 本身不通過 R1；M5 前不得宣稱 R1 或第一可用版本完成。

## M6 — PDF and legislative depth（未來）

**依賴：** M5。

**內容：** 加入 PyMuPDF 預設 PDF extraction、`marker-pdf` optional fallback、
OCR fallback，以及更完整的立法、預算與程序資料 extraction、page mapping、
review metadata。

**驗收：** PDF/parser snapshot fixtures 覆蓋正常、低品質與 image-only 路徑；
Marker 不在預設安裝或路徑中；程序事件、預算欄位、page mapping 與 review
結果可追溯，且 CPU-heavy 工作不阻塞 async loop。

## M7 — Source expansion and full Phase 1 CLI（未來）

**依賴：** M5、M6。

**內容：** 逐一加入 additional sources（例如 PPG、媒體與其他規劃來源），
並完成 `reparse`、`export` 及 Phase 1 CLI 全部規劃命令。來源只有在有 adapter、
fixtures、attribution、error handling 與 dedup tests 後才可啟用。

**驗收：** 每個 additional source 有獨立 fixture/contract coverage；reparse
不覆寫 revision；CSV/Parquet export 可重現；完整 Phase 1 CLI、documentation、
regression/integration tests 與 x86 Synology image/build validation 通過。
