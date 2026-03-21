# Architecture Scalability Review

**Date:** 2026-03-21
**Estimated capacity before fixes:** ~50-100 concurrent users
**Estimated capacity after fixes:** ~500+ concurrent users

---

## Issues Fixed

### 1. Missing Database Indexes — FIXED
Added 9 indexes to `database.py` covering all foreign keys used in WHERE/JOIN clauses:
- `children.family_id`, `stories(family_id, status)`, `story_sentences.story_id`
- `story_words.sentence_id`, `sessions.child_id`, `sessions.story_id`
- `session_words.session_id`, `generation_jobs.story_id`, `generation_logs.job_id`

### 2. N+1 Query Patterns — FIXED

**children.py — list_children():** Replaced per-child stats loop with a single `LEFT JOIN LATERAL` query that fetches children + aggregated session stats in one round trip.

**stories.py — list_stories():** Added `_build_story_responses_batch()` that fetches all sentences with `ANY($1)`, then all words with `ANY($1)`, and groups in Python. Listing 10 stories now takes 3 queries instead of 61.

**stories.py — get_story():** `_build_story_response()` now fetches all words for all sentences in one query using `ANY($1)` instead of one query per sentence.

**parent.py — get_all_analytics():** Extracted `_get_child_analytics()` helper that combines COUNT + AVG into a single query per child (was 3 queries per child).

### 3. No Pagination — FIXED
Added `limit`/`offset` query parameters to all list endpoints:
- `GET /api/stories/` — default 50, max 200
- `GET /api/children/` — default 50, max 200
- `GET /api/sessions/child/{id}` — default 50, max 200
- `GET /api/generation/jobs` — default 50, max 200

Constants defined in `models/api_models.py` (`DEFAULT_PAGE_LIMIT`, `MAX_PAGE_LIMIT`).

### 4. Single-Job Worker — FIXED
Changed `worker.py`:
- `max_jobs`: 1 → 4
- `job_timeout`: 10min → 30min
- `max_job_retries`: 1 → 3
- `queue_read_limit`: 1 → 4

### 5. JWT Secret Race Condition — FIXED
Removed file-writing from `config.py` validator. Now logs a warning if `JWT_SECRET` is not set instead of silently generating different secrets per process. Multi-worker deployments must set `JWT_SECRET` in `.env`.

### 6. Rate Limiting Race Condition — FIXED
Replaced separate `INCR` + `EXPIRE` calls with an atomic Lua script in `rate_limit.py`. The counter increment and TTL set happen in a single Redis round-trip — no window for the key to get stuck without an expiry.

### 7. TTS Semaphore — FIXED
Increased from 1 → 3 in `tts_service.py` to allow concurrent GPU inference ops.

### 8. ComfyUI Polling — FIXED
Replaced fixed 2-second polling interval with exponential backoff (1s → 1.5s → 2.25s → ... → max 10s) in `comfyui_client.py`. Also increased HTTP client timeout from 30s → 300s to match actual generation times.

### 9. Request Timeouts — FIXED
Added `request_timeout_middleware` in `main.py` that returns 504 after configurable timeout (default 30s via `REQUEST_TIMEOUT` setting).

### 10. Health Check Depth — FIXED
Added `GET /api/health/ready` endpoint in `main.py` that checks database connectivity (`SELECT 1`) and Redis (`PING`). Returns 503 with details if any dependency is down.

### 11. Database Pool Size — FIXED
Made pool size configurable via `DB_POOL_MIN` (default 5) and `DB_POOL_MAX` (default 20) in `config.py`. Increased `min_size` from 2 → 5 for better connection reuse.

---

## Remaining Issues (Short-term)

### Separate Redis Instances
The app uses one Redis for rate limiting, job queue, and session tokens. A Redis restart loses all three. Should split into at least two: one for the job queue, one for everything else.

### PgBouncer for Connection Pooling
With multiple API workers + arq workers each running their own asyncpg pool, PostgreSQL's connection limit can be reached. Adding PgBouncer as an infrastructure-level pooler would solve this.

### ComfyUI Health Polling on Start
`_manage_comfyui("start")` still uses a hardcoded 10-second sleep. Should poll the ComfyUI health endpoint until ready.

### Job Deduplication
Two identical generation requests still create two jobs. Should check for pending jobs with the same topic/difficulty/theme before enqueuing.

---

## Remaining Issues (Medium-term)

### Response Caching
Frequently accessed story lists and details should be cached in Redis with a short TTL (60s) to avoid repeated DB queries.

### Materialized Views for Analytics
The commonly-missed-words query joins 3 tables with GROUP BY. A materialized view refreshed periodically would make the parent dashboard instant.

### Read Replicas
Analytics queries should run against a read replica to avoid competing with write operations.

### TTS/Whisper as Separate Services
GPU-bound services should be separated from the API process and scaled independently.

### CDN for Assets
Generated images and audio should be served from a CDN rather than the API server.

---

## Single Points of Failure

| Component | Failure Impact | Mitigation |
|---|---|---|
| PostgreSQL (1 instance) | All reads/writes fail | Add read replica, connection pooling |
| Redis (1 instance) | Rate limiting, job queue, sessions all lost | Separate instances, Redis Sentinel |
| Ollama (1 URL) | Story text generation impossible | Multiple Ollama instances behind LB |
| ComfyUI (1 URL) | Image generation impossible | Queue-based with multiple workers |
| F5-TTS (in-process) | Audio generation fails | Separate microservice |
| Whisper (in-process) | Speech recognition unavailable | Separate microservice |
