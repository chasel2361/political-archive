# Political Archive Crawler — Project Specification

## 1. Goal

建立一個可定期執行的政治人物資料蒐集系統，用於：

* 爬取指定政治人物相關公開資料
* 保存原始證據
* 將 HTML、JSON、PDF、逐字稿整理為統一格式
* 擷取人物、法案、預算、程序事件與媒體報導關聯
* 寫入 PostgreSQL
* 支援每兩週自動更新及手動執行
* 開發環境為 Ubuntu
* 正式部署至 Intel x86 Synology NAS
* 使用 Docker Compose
* 使用 `uv` 管理 Python、venv 與 dependencies

第一階段只建立：

```text
Crawler + document pipeline + PostgreSQL
```

暫不建立：

* Web frontend
* FastAPI
* Redis
* Celery
* OpenSearch
* pgvector
* LLM service
* IVOD 影片下載

---

## 2. Technology

```text
Python 3.12
uv
PostgreSQL 16
SQLAlchemy 2
Alembic
Pydantic 2
Typer
httpx
asyncio
BeautifulSoup4
lxml
PyMuPDF
PyMuPDF4LLM
Marker optional fallback
OCR optional fallback
zstandard
pytest
pytest-asyncio
ruff
mypy
Docker Compose
```

Use `psycopg` as the PostgreSQL driver.

Prefer synchronous SQLAlchemy unless asynchronous database access provides a clear benefit. Network crawling should be asynchronous.

---

## 3. Architecture

```text
Ubuntu cron / Synology Task Scheduler / manual CLI
                         │
                         ▼
                 one-shot crawler
                         │
            ┌────────────┴────────────┐
            ▼                         ▼
     async source adapters       document pipeline
     API / RSS / HTML / PDF      parse / OCR / normalize
            │                         │
            └────────────┬────────────┘
                         ▼
                    PostgreSQL
                         │
                         ▼
               compressed file storage
            PDF / HTML.zst / JSON.zst / MD.zst
```

Docker services:

```text
db
crawler
```

The crawler container should normally run as a one-shot command.

---

## 4. Project Structure

```text
political-archive/
├── pyproject.toml
├── uv.lock
├── compose.yml
├── Dockerfile
├── .env.example
├── .gitignore
├── README.md
├── PROJECT_SPEC.md
│
├── config/
│   ├── people.yml
│   └── sources.yml
│
├── src/
│   └── political_archive/
│       ├── __init__.py
│       ├── __main__.py
│       ├── cli.py
│       ├── config.py
│       ├── db.py
│       ├── models.py
│       ├── storage.py
│       ├── pipeline.py
│       ├── crawl.py
│       ├── dedup.py
│       ├── exceptions.py
│       │
│       ├── sources/
│       │   ├── __init__.py
│       │   ├── base.py
│       │   ├── legislature/
│       │   │   ├── __init__.py
│       │   │   ├── bills.py
│       │   │   ├── ppg.py
│       │   │   ├── ivod.py
│       │   │   └── budget.py
│       │   └── media/
│       │       ├── __init__.py
│       │       ├── cna.py
│       │       ├── pts.py
│       │       └── factcheck.py
│       │
│       └── parsers/
│           ├── __init__.py
│           ├── html.py
│           ├── pdf.py
│           ├── ocr.py
│           ├── bill.py
│           └── budget.py
│
├── migrations/
├── tests/
│   ├── fixtures/
│   ├── unit/
│   └── integration/
│
├── data/
│   ├── source/
│   ├── normalized/
│   ├── temporary/
│   ├── exports/
│   └── backups/
│
├── logs/
└── scripts/
    ├── crawl.sh
    ├── backup.sh
    └── restore.sh
```

Avoid unnecessary abstraction layers during the first phase.

---

## 5. uv Setup

Initialize the project with:

```bash
uv init --package
uv python pin 3.12
```

Add dependencies:

```bash
uv add \
  sqlalchemy \
  psycopg[binary] \
  alembic \
  pydantic \
  pydantic-settings \
  typer \
  httpx \
  beautifulsoup4 \
  lxml \
  pymupdf \
  pymupdf4llm \
  pyyaml \
  zstandard
```

Development dependencies:

```bash
uv add --dev \
  pytest \
  pytest-asyncio \
  pytest-cov \
  ruff \
  mypy
```

Optional PDF dependencies should use an extra group:

```toml
[project.optional-dependencies]
pdf-full = [
    "marker-pdf",
]
```

Run commands with:

```bash
uv run political-archive --help
uv run pytest
uv run ruff check .
uv run mypy src
```

Do not manually create or manage `.venv`. Let `uv` manage it.

---

## 6. CLI

Create a Typer CLI with the executable:

```text
political-archive
```

Required commands:

```bash
political-archive crawl
political-archive crawl --source legislature
political-archive crawl --source cna
political-archive crawl --person "人物名稱"
political-archive crawl --from-date 2026-01-01
political-archive crawl --to-date 2026-07-13

political-archive fetch-url URL
political-archive reparse
political-archive reparse --source ppg
political-archive status

political-archive cleanup-temp --approved-only
political-archive cleanup-temp --approved-only --dry-run

political-archive export --format csv
political-archive export --format parquet

political-archive db-upgrade
```

All commands must return non-zero exit codes on failure.

---

## 7. Source Adapter Interface

Use an asynchronous interface.

```python
from collections.abc import AsyncIterator
from typing import Protocol


class SourceAdapter(Protocol):
    name: str

    async def discover(
        self,
        since: str | None = None,
        until: str | None = None,
    ) -> AsyncIterator["DiscoveredItem"]:
        ...

    async def fetch(
        self,
        item: "DiscoveredItem",
    ) -> "RawDocument":
        ...

    def parse(
        self,
        raw: "RawDocument",
    ) -> "ParsedDocument":
        ...
```

Each adapter is responsible only for:

* discovering source items
* downloading source content
* parsing source-specific metadata
* returning normalized documents

Person matching, deduplication and legislative extraction belong to shared pipeline modules.

---

## 8. Async Crawling

Use `httpx.AsyncClient`.

Default limits:

```text
global concurrency: 5
per-domain concurrency: 2
request timeout: 30 seconds
retry count: 3
```

Implement:

* bounded semaphore
* per-domain concurrency
* retry with exponential backoff
* `Retry-After` support
* ETag
* Last-Modified
* content type validation
* response size limits
* atomic file writes

Do not bypass login, paywalls, CAPTCHAs or access controls.

CPU-heavy operations must not block the event loop.

Use `asyncio.to_thread` or a process executor for:

* PDF extraction
* OCR
* Marker
* large-file hashing

Concurrency limits:

```text
HTML/API fetch: 5
PDF parsing: 1
Marker: 1
OCR: 1
```

---

## 9. Document Pipeline

Processing order:

```text
discover
fetch
hash
store source
parse
normalize
identify tracked people
extract legislative data
deduplicate
write database
record crawl result
```

PDF processing order:

```text
PyMuPDF text extraction
        │
        ├── quality acceptable → Markdown
        │
        └── quality poor
                ↓
              Marker
                │
                └── still poor / image-only
                        ↓
                       OCR
```

OCR and Marker should be fallbacks, not the default path.

---

## 10. Storage Policy

Directory structure:

```text
data/
├── source/
│   ├── pdf/
│   ├── html/
│   └── json/
├── normalized/
│   └── markdown/
├── temporary/
│   ├── rendered-pages/
│   ├── ocr/
│   └── marker-cache/
├── exports/
└── backups/
```

Permanent formats:

```text
PDF        original .pdf
HTML       .html.zst
JSON       .json.zst
Markdown   .md.zst
```

Use Zstandard for text-based source and normalized files.

Keep:

* original PDF
* compressed source HTML or JSON
* final normalized Markdown
* SHA-256 hash
* source URL
* parser name and version
* page mapping
* review result

Delete after approval:

* rendered page images
* OCR preprocessing images
* Marker cache
* unused conversion outputs
* OCR intermediate files

The cleanup command must require:

```text
review_status = APPROVED
normalized output exists
source PDF exists
hashes recorded
database transaction completed
```

Always support `--dry-run`.

Do not download IVOD video. Save URL, metadata and timestamps only.

---

## 11. Data Model

Initial tables:

```text
person
person_alias
source
document
document_revision
document_person
legislative_item
legislative_person
procedure_event
crawl_run
review_override
```

### person

```text
id
canonical_name
party
constituency
term
active_from
active_to
metadata_json
```

### person_alias

```text
id
person_id
alias
alias_type
```

### source

```text
id
name
source_type
base_url
enabled
last_success_at
cursor_json
```

### document

```text
id
source_id
external_id
canonical_url
document_type
title
author
published_at
first_seen_at
last_seen_at
current_revision_id
```

### document_revision

```text
id
document_id
content_hash
raw_path
normalized_path
parsed_text
metadata_json
parser_name
parser_version
created_at
review_status
```

Create a new revision only when the content hash changes.

### document_person

```text
document_id
person_id
relation_type
confidence
```

Allowed relation types:

```text
mentioned
speaker
proposer
co_proposer
cosigner
commented_on
fact_checked
```

### legislative_item

Use one initial table for bills and fiscal actions.

```text
id
item_type
title
external_id
origin_type
fiscal_year
agency
program
proposed_amount
approved_amount
status
parent_item_id
source_document_id
metadata_json
```

Allowed item types:

```text
bill
bill_version
annual_budget
special_budget
fiscal_legislative_proposal
alternative_spending_plan
budget_cut
budget_freeze
unfreeze
main_resolution
attached_resolution
```

### legislative_person

```text
legislative_item_id
person_id
role
```

Allowed roles:

```text
primary_proposer
co_proposer
cosigner
supporter
opponent
procedure_initiator
```

### procedure_event

```text
id
legislative_item_id
event_type
event_date
description
result
source_document_id
metadata_json
```

Important event types:

```text
agenda_listed
agenda_withheld
deferred
objection_raised
referred_to_committee
referral_blocked
returned_to_procedure_committee
committee_review
caucus_negotiation
second_reading
third_reading
reconsideration
withdrawn
```

### crawl_run

```text
id
source_id
started_at
finished_at
status
discovered_count
downloaded_count
parsed_count
failed_count
error_summary
```

---

## 12. Deduplication

Use:

```text
source external ID
canonical URL
SHA-256 normalized content hash
```

Later add SimHash or MinHash only if syndicated news duplication becomes significant.

Never overwrite source revisions.

---

## 13. Configuration

### config/people.yml

```yaml
people:
  - id: person-example
    canonical_name: 範例人物
    aliases:
      - 範例委員
    enabled: true
```

### config/sources.yml

```yaml
sources:
  legislature:
    enabled: true
    concurrency: 2
    requests_per_second: 1.0

  cna:
    enabled: true
    concurrency: 2
    requests_per_second: 0.5

  pts:
    enabled: false
    concurrency: 2
    requests_per_second: 0.5
```

Configuration should be validated using Pydantic.

---

## 14. Scheduling

The crawler should not require a persistent scheduler service.

Recommended execution:

```bash
docker compose run --rm crawler crawl
```

Synology Task Scheduler or Ubuntu cron should run it every two weeks.

Keep manual execution available at all times.

Use an overlap window when crawling incrementally:

```text
last successful date minus 3 days
```

This reduces missed records caused by delayed publishing or modified timestamps.

Deduplication must prevent repeated insertion.

---

## 15. Docker

### compose.yml

Provide:

```text
db
crawler
```

The database should run continuously.

The crawler should run as a one-shot container.

Persist:

```text
PostgreSQL data
data/
logs/
config/
```

Do not expose PostgreSQL publicly.

### Dockerfile

Use a Python 3.12 slim base image.

Install the project with `uv`.

Use a multi-stage build where practical.

The runtime command should call the installed CLI directly.

---

## 16. Database Migrations

Use Alembic.

Required workflow:

```bash
uv run alembic revision --autogenerate -m "initial schema"
uv run alembic upgrade head
```

Add a CLI wrapper:

```bash
political-archive db-upgrade
```

The application must not silently create or mutate the production schema outside migrations.

---

## 17. Logging

Log to stdout and rotating files.

Include:

```text
timestamp
level
source
crawl_run_id
document_id
URL
event
error type
```

Do not log:

* database passwords
* API keys
* full environment variables

Use structured JSON logs if simple to implement. Plain structured text is acceptable for the first version.

---

## 18. Testing

Create:

```text
unit tests
parser snapshot tests
database integration tests
CLI tests
```

Required unit coverage:

* URL canonicalization
* SHA-256 deduplication
* Zstandard read/write
* amount parsing
* percentage parsing
* date parsing
* person alias matching
* cleanup safety rules

Store small source fixtures under:

```text
tests/fixtures/
```

Do not make normal unit tests depend on live websites.

Mark live contract tests separately:

```bash
pytest -m live
```

---

## 19. Code Quality

Configure Ruff for:

```text
linting
formatting
import sorting
```

Use type hints for public functions.

Run before completion:

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest
```

Prefer small, explicit modules over framework-heavy abstractions.

---

## 20. Initial Implementation Order

Implement in this order:

```text
1. uv project and pyproject.toml
2. configuration loading
3. PostgreSQL connection
4. SQLAlchemy models
5. Alembic migrations
6. compressed file storage
7. crawl_run tracking
8. SourceAdapter protocol
9. async HTTP fetcher
10. one simple legislature adapter
11. raw and normalized document pipeline
12. person alias matching
13. legislative item extraction
14. CLI commands
15. Docker Compose
16. tests
17. backup and cleanup scripts
```

Do not implement all source adapters initially.

The first working adapter should demonstrate:

```text
discover
fetch
store
parse
normalize
deduplicate
database insert
crawl status
```

---

## 21. First Milestone Acceptance Criteria

The first milestone is complete when:

* `uv sync` creates a working environment
* PostgreSQL starts through Docker Compose
* Alembic migrations succeed
* one source adapter can retrieve real records
* original source content is saved
* normalized Markdown is saved as `.md.zst`
* duplicate documents are not inserted twice
* tracked people are associated with documents
* crawl results are recorded
* manual CLI execution works
* Docker one-shot execution works
* tests pass
* temporary files can be safely cleaned with `--dry-run`
* database backup and restore scripts exist

Focus first on reliable data collection and traceability. Defer search applications, semantic analysis and frontend development until enough validated data has accumulated.
