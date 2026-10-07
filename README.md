# Bulk Certificate Generator

A production-quality FastAPI service that accepts one bulk request, validates each recipient independently, generates PDF certificates asynchronously, tracks progress, isolates individual failures, and serves completed PDFs for download.

---

## Architecture

```
Client
  ↓
FastAPI (API routes — thin HTTP adapters)
  ↓
Service layer (GenerationService, CertificateService, ValidationService)
  ↓
PostgreSQL (source of truth for job/certificate state)

FastAPI
  ↓
Redis (Celery broker)
  ↓
Celery dispatcher task
  ↓
Celery batch worker tasks
  ↓
CertificateService → ReportLab PDF generator → StorageService → local filesystem
```

### Why this stack?

| Decision | Reason |
|---|---|
| **FastAPI** | Native async, automatic OpenAPI docs, Pydantic integration, excellent performance |
| **Celery** | Battle-tested distributed task queue; retry/ack safety; concurrency without coding it from scratch |
| **Redis** | Lightweight Celery broker; no persistence required for the broker |
| **PostgreSQL** | Transactional ACID guarantees for job/certificate state; `RETURNING` for atomic claim |
| **PDFs on filesystem** | Binary blobs in Postgres harm performance and backup size; filesystem is simpler and faster |
| **Batch processing** | A 500-recipient job is split into batches of 50; workers run batches concurrently |
| **Individual failure isolation** | Each certificate is wrapped in its own try/except; one bad name never stops the rest |

---

## Setup (local, no Docker)

### Requirements

- Python ≥ 3.11
- PostgreSQL 14+
- Redis 7+

### Environment

```bash
cp .env.example .env
# Edit .env with your local DATABASE_URL and REDIS_URL
```

### Install dependencies

```bash
python -m pip install -r requirements.txt
```

### Database migrations

```bash
# Set DATABASE_URL to a psycopg2-compatible URL (alembic runs sync)
export DATABASE_URL=postgresql+psycopg2://certuser:certpass@localhost:5432/certdb

alembic upgrade head
```

### Start the API

```bash
uvicorn app.main:app --reload
```

### Start a Celery worker

```bash
celery -A app.worker.celery_app worker --loglevel=info --concurrency=4
```

---

## Docker Compose (recommended)

```bash
# Start all services
docker compose up --build

# Run migrations inside the api container
docker compose exec api alembic upgrade head
```

Services:
- `postgres` — port 5432
- `redis` — port 6379
- `api` — port 8000 (`http://localhost:8000`)
- `worker` — Celery, 4 concurrent processes

Generated PDFs are persisted in a named Docker volume (`certificate_storage`) shared between `api` and `worker`.

---

## API Usage

### 1. Create a generation job

```bash
curl -X POST http://localhost:8000/api/v1/generation-jobs \
  -H "Content-Type: application/json" \
  -d '{
    "certificate": {
      "title": "Certificate of Completion",
      "event_name": "Python Bootcamp 2026",
      "issuer_name": "Example Organization",
      "issue_date": "2026-10-07"
    },
    "recipients": [
      {"name": "Alice Johnson", "email": "alice@example.com"},
      {"name": "Bob Smith"},
      {"name": "   "}
    ]
  }'
```

**202 Response:**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "queued",
  "total_count": 3,
  "successful_count": 0,
  "failed_count": 1,
  "status_url": "/api/v1/generation-jobs/550e8400-e29b-41d4-a716-446655440000"
}
```

> `failed_count: 1` is immediate — the blank name was rejected without blocking the other two.

### 2. Poll job status

```bash
curl http://localhost:8000/api/v1/generation-jobs/550e8400-e29b-41d4-a716-446655440000
```

**200 Response:**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed_with_errors",
  "total_count": 3,
  "successful_count": 2,
  "failed_count": 1,
  "pending_count": 0,
  "progress_percent": 100.0,
  "created_at": "2026-10-07T12:00:00",
  "started_at": "2026-10-07T12:00:01",
  "completed_at": "2026-10-07T12:00:05",
  "results_url": "/api/v1/generation-jobs/550e8400-e29b-41d4-a716-446655440000/certificates"
}
```

### 3. List certificates

```bash
curl "http://localhost:8000/api/v1/generation-jobs/550e8400-e29b-41d4-a716-446655440000/certificates?page=1&page_size=50"

# Filter by status
curl "...?status=failed"
```

**200 Response:**
```json
{
  "job_id": "550e8400-...",
  "total": 3,
  "page": 1,
  "page_size": 50,
  "items": [
    {
      "certificate_id": "aaa-...",
      "status": "completed",
      "recipient_name": "Alice Johnson",
      "recipient_email": "alice@example.com",
      ...
    },
    {
      "certificate_id": "bbb-...",
      "status": "failed",
      "recipient_name": "(invalid)",
      "error_code": "NAME_EMPTY",
      "error_message": "Recipient name cannot be blank.",
      ...
    }
  ]
}
```

### 4. Download a PDF

```bash
curl -OJ http://localhost:8000/api/v1/certificates/aaa-...
# Saves: aaa-....pdf
```

- `200 application/pdf` — completed certificate
- `409` — not yet ready (pending/processing) or generation failed
- `404` — unknown certificate ID

### 5. Health checks

```bash
curl http://localhost:8000/health/live    # {"status": "ok"}
curl http://localhost:8000/health/ready   # {"status": "ok"}
```

---

## Testing

```bash
# All tests (unit + integration API, no live DB required)
pytest

# Unit tests only (PDF generator + validation logic, no dependencies)
pytest tests/unit/ -v

# With verbose output
pytest -v
```

> Integration tests use mocked repositories and storage — no live PostgreSQL or Redis is needed to run the test suite.

---

## Configuration reference

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://...` | Async PostgreSQL connection string |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis URL for Celery broker |
| `STORAGE_ROOT` | `storage` | Filesystem root for generated PDFs |
| `MAX_RECIPIENTS_PER_JOB` | `500` | Hard cap per request |
| `BATCH_SIZE` | `50` | Certificates per Celery batch task |
| `CERTIFICATE_FONT_PATH` | `` | Optional TTF font path (empty = Helvetica built-in) |
| `LOG_LEVEL` | `INFO` | Python logging level |

---

## Project structure

```
app/
├── main.py               # FastAPI application factory + global exception handlers
├── api/routes/           # Thin HTTP adapters (no SQL, no PDF logic)
├── core/                 # config, logging, exception hierarchy
├── db/                   # SQLAlchemy engine + session factory
├── models/               # ORM models (GenerationJob, Certificate)
├── schemas/              # Pydantic I/O schemas
├── repositories/         # All SQL queries (no business logic)
├── services/             # Business orchestration
│   ├── generation_service.py   # Create job + dispatch
│   ├── certificate_service.py  # Claim → generate → store → complete
│   ├── validation_service.py   # Per-recipient validation
│   └── storage_service.py      # Atomic file I/O
├── certificate/
│   ├── template.py       # All layout constants
│   └── generator.py      # ReportLab PDF rendering
└── worker/
    ├── celery_app.py     # Celery configuration
    └── tasks.py          # Thin orchestration tasks
```
