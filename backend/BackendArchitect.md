# Backend Architect — Bee4You

> **Purpose of this file.** This is the single source of truth for how the Bee4You backend is built.
> Before (and after) every backend prompt, check the change against this document.
> If a change needs to break a rule here, **update this file first** (and add a line to the Decision Log at the bottom) — never let the code and this file drift apart.

---

## 0. Quick checklist for every backend prompt

Run through this list before accepting any backend change:

- [ ] **Schema changes go through a migration** in `backend/supabase/migrations/`. SQLAlchemy never creates or alters tables.
- [ ] **Every new table** has: client-generated `uuid` PK, `owner_id`, `created_at`, `updated_at`, `client_updated_at`, `deleted_at`, an RLS policy, and an index on `owner_id`.
- [ ] **Every new table that devices need** is added to: `backend/powersync/sync-rules.yaml`, the `powersync` publication (`alter publication powersync add table ...` in the migration), `app/services/registry.py` (if devices write it), and the frontend PowerSync schema (see `frontend/FrontendArchitect.md`).
- [ ] **Every write is an idempotent upsert by `id`.** Retrying the same request must never create a duplicate.
- [ ] **Every query is scoped to the current user** (RLS via `set local` claims *and* `owner_id` filter in code).
- [ ] **Business logic lives in `services/`**, not in routers and not in the LangGraph nodes. Typed and voice entries call the *same* service function.
- [ ] **No secrets in code or in the app.** `ANTHROPIC_API_KEY`, `DATABASE_URL`, JWT secrets live only in server env vars.
- [ ] **The LLM only extracts.** Matching colonies/products, validation, and saving are plain code.
- [ ] **Nothing is saved from voice without an explicit "yes"** after the summary (amounts always read back).
- [ ] **Pydantic models for every request/response** (they generate the OpenAPI docs the frontend relies on).
- [ ] **Tests added/updated** in `backend/tests/` for the service logic you touched.
- [ ] The change belongs to the **current roadmap phase** (section 12) — or you consciously decided otherwise.

---

## 1. What the backend is responsible for

Bee4You is an **offline-first** mobile field notebook for beekeepers. The phone is the primary place where data is created; the backend is where it is **made durable, validated, shared across devices, and enriched by the voice assistant**.

The backend consists of three cooperating parts:

| Part | Responsibility | Talks to |
| --- | --- | --- |
| **Supabase** | Auth (JWT issuer), Postgres + PostGIS (central database), Storage (photos, voice audio), Row Level Security | App (auth, storage), PowerSync, FastAPI |
| **PowerSync service** | Streams server rows *down* to each device's SQLite according to sync rules | Supabase Postgres (replication), App |
| **FastAPI (Python)** | Receives the device upload queue, runs the voice assistant (LangGraph + Claude), holds logic too complex for direct DB access | Supabase Postgres, Anthropic API, App |

```text
Mobile app ── sign-in / storage ─────────────► Supabase Auth + Storage
Mobile app ◄── downstream sync (read) ──────── PowerSync service ◄── Postgres replication
Mobile app ── upload queue + voice (write) ──► FastAPI ──► Postgres (SQLAlchemy async)
                                                  └──► Claude (LangChain / LangGraph)
```

**Key principle:** data flows **down** through PowerSync and **up** through FastAPI. The app never writes to Postgres tables directly via supabase-js (only Auth and Storage use supabase-js).

**One login, one database:** the app sends the same Supabase access token to FastAPI. FastAPI verifies it; there is no second user system.

---

## 2. Technology stack (fixed — do not swap without a Decision Log entry)

| Technology | Role | Rules |
| --- | --- | --- |
| Supabase Auth | Sign-in (email, Google, Apple); issues JWTs | Only JWT issuer. `sub` claim = user id = `owner_id`. |
| Supabase Postgres + PostGIS | Central records, apiary locations | Schema owned by migrations only. |
| Row Level Security | Users only see/change their own rows | Enabled on **every** table in `public`. |
| Supabase Storage | Hive photos, voice recordings | Private buckets; path prefix = `{user_id}/...`. |
| Supabase CLI migrations | Own the schema | `backend/supabase/migrations/*.sql`, timestamped, never edited after being applied to the hosted project. |
| PowerSync service | Streams changes to devices | Rules in `backend/powersync/sync-rules.yaml`. |
| Python 3.12+, `uv` | Runtime & env/deps management | Commit `uv.lock`. |
| FastAPI + Pydantic v2 | HTTP API, validation, OpenAPI | Async endpoints only. |
| SQLAlchemy 2.x (async) + asyncpg | DB reads/writes from FastAPI | **Never** `create_all()`, never Alembic. Models mirror migrations. |
| PyJWT | Verify Supabase JWTs | Prefer JWKS (asymmetric); HS256 secret only as fallback. |
| LangGraph | Voice-entry conversation graph | Interrupts for "ask" and "confirm". |
| LangChain + langchain-anthropic | Claude calls with structured output | Default model: Claude Haiku (speed/cost). |
| langgraph-checkpoint-postgres | Persist conversations between requests | Uses the same Postgres, own schema/tables. |
| LangSmith (optional) | Trace graph runs | Enabled only via env var; no PII in tags. |

---

## 3. Folder layout

Everything backend-related lives under `backend/`:

```text
backend/
├── BackendArchitect.md          # ← this file
├── pyproject.toml               # deps managed with uv
├── uv.lock
├── .env.example                 # every env var, no real values
├── app/
│   ├── main.py                  # FastAPI app factory, router registration, lifespan (DB pool, checkpointer)
│   ├── config.py                # pydantic-settings Settings; the ONLY place env vars are read
│   ├── db.py                    # async engine, session factory, `user_session()` that sets RLS claims
│   ├── errors.py                # AppError + handlers → {"error": {...}} responses
│   ├── api/                     # FastAPI routers — thin: parse, call service, return
│   │   ├── deps.py              # get_current_user, get_db
│   │   ├── health.py
│   │   ├── me.py                # GET /v1/me
│   │   ├── sync.py              # POST /v1/sync/upload  (PowerSync upload queue)
│   │   ├── voice.py             # /v1/voice/...         (assistant)
│   │   └── records.py           # complex reads (e.g. colony history) if needed
│   ├── auth/
│   │   └── jwt.py               # Supabase JWT verification (JWKS + fallback)
│   ├── models/
│   │   ├── db/                  # SQLAlchemy ORM models (mirror of migrations)
│   │   └── schemas/             # Pydantic request/response + domain drafts
│   ├── services/                # Domain logic shared by typed AND voice entries
│   │   ├── apiaries.py
│   │   ├── colonies.py          # incl. moves / placements
│   │   ├── treatments.py
│   │   ├── harvests.py
│   │   ├── inventory.py
│   │   ├── notes.py
│   │   ├── registry.py          # which tables devices may write, validation model, hooks
│   │   ├── sync.py              # generic idempotent LWW upsert + conflict logging
│   │   └── resolve.py           # "hive 12" → colony id, product → inventory item (plain code)
│   └── assistant/
│       ├── graph.py             # LangGraph StateGraph definition
│       ├── state.py             # graph state TypedDict / Pydantic
│       ├── nodes/               # extract, resolve, ask, confirm, save
│       ├── prompts/             # prompt templates (versioned, plain text)
│       └── llm.py               # model factory (ChatAnthropic), structured output helpers
├── tests/
│   ├── conftest.py              # test DB, fake user, fake LLM
│   ├── services/
│   ├── api/
│   └── assistant/
├── supabase/
│   ├── config.toml
│   ├── migrations/              # schema, RLS policies, PostGIS, indexes
│   └── seed.sql                 # local dev data only
└── powersync/
    └── sync-rules.yaml          # which rows each user's devices receive
```

**Layering rule (strict):** `api → services → models/db`. `assistant/nodes → services`. Routers never touch SQLAlchemy directly; services never import FastAPI; assistant nodes never write SQL.

---

## 4. Domain model

### 4.1 Concepts

- **Apiary** — a site (permanent or temporary) with a location. Shown as a pin on the map.
- **Colony** — a hive. Either `stationary` (stays at one apiary) or `migratory` (moves during the season).
- **Placement** — "colony X was at apiary Y from date A to date B". A **move** = close the current placement + open a new one. This is how earlier visits stay linked to the site where they happened.
- **Field records** — things logged at the hive: **treatment**, **harvest**, **inventory adjustment**, **note/inspection**. Every record stores the `apiary_id` *where it happened* (not just the colony), so history survives moves.
- **Inventory item** — a product or piece of equipment (oxalic acid, strips, supers…). Stock = sum of adjustments (append-only).
- **Voice note** — a transcript captured offline, processed by the assistant once online.
- **Sync conflict** — a record two devices edited concurrently; kept for review.

### 4.2 Tables (Postgres, schema `public`)

Common columns on **every** domain table:

| Column | Type | Notes |
| --- | --- | --- |
| `id` | `uuid` PK | **Generated on the device**, never by the server (no `default gen_random_uuid()` reliance for client tables). |
| `owner_id` | `uuid` not null → `auth.users(id)` | Set server-side from the JWT `sub`, never trusted from the payload. |
| `created_at` | `timestamptz` default `now()` | Server time. |
| `updated_at` | `timestamptz` default `now()` | Server time, updated by trigger. |
| `client_updated_at` | `timestamptz` not null | Device time of last edit — used for last-write-wins. |
| `deleted_at` | `timestamptz` null | **Soft delete.** Sync needs tombstones; never hard-delete user records. |

Domain tables (columns beyond the common ones):

| Table | Key columns |
| --- | --- |
| `profiles` | `id = auth.users.id`, `owner_id` (generated = `id`), `display_name`, `locale` (speech/UI language). Created by a trigger on sign-up; devices may only PUT/PATCH their own. |
| `apiaries` | `name`, `location geography(Point,4326)`, `kind` (`permanent` / `temporary`), `notes` |
| `colonies` | `label` (e.g. "Hive 12"), `number int` (for voice matching), `mode` (`stationary` / `migratory`), `status` (`active` / `dead` / `sold` / `merged`), `queen_year`, `notes` |
| `colony_placements` | `colony_id`, `apiary_id`, `started_at`, `ended_at` (null = current). **Partial unique index:** one open placement per colony (`where ended_at is null and deleted_at is null`). |
| `inventory_items` | `name`, `category` (`treatment` / `equipment` / `consumable` / `other`), `unit`, `apiary_id` (null = home/store) |
| `inventory_adjustments` | `item_id`, `delta numeric`, `unit`, `reason` (`purchase` / `used` / `moved` / `correction`), `apiary_id`, `adjusted_at`, `treatment_id` (null unless auto-created by a treatment) |
| `treatments` | `colony_id`, `apiary_id`, `inventory_item_id` (nullable), `product_name` (denormalized text), `amount numeric`, `unit`, `treated_at`, `notes`, `source` (`manual` / `voice`) |
| `harvests` | `apiary_id`, `colony_id` (nullable — harvest can be apiary-level), `quantity numeric`, `unit`, `harvested_at`, `notes`, `source` |
| `colony_notes` | `colony_id`, `apiary_id`, `noted_at`, `queen_seen bool`, `temperament` (`calm` / `nervous` / `aggressive`), `text`, `source` |
| `attachments` | `colony_id` / `apiary_id` / `record_type` + `record_id`, `storage_path`, `kind` (`photo` / `audio`) |
| `voice_notes` | `transcript`, `audio_path`, `locale`, `context_colony_id`, `context_apiary_id`, `status` (`pending` / `processing` / `needs_answer` / `needs_confirmation` / `saved` / `failed`), `thread_id`, `result_record_type`, `result_record_id`, `error` |
| `sync_conflicts` | `table_name`, `record_id`, `client_payload jsonb`, `server_payload jsonb`, `resolved_at`, `resolution` |

**Units** are a fixed enum shared with the frontend: `ml`, `l`, `g`, `kg`, `pcs`, `strips`, `frames`. Add new units only via migration + both architect files.

**Amounts** are `numeric`, never float. Dates of events (`treated_at`, etc.) are `timestamptz`, stored UTC.

### 4.3 PostGIS ↔ SQLite

SQLite on the device has no PostGIS. Therefore:

- Postgres stores `apiaries.location` as `geography(Point,4326)`.
- Sync rules expose it as plain `lat` / `lng` columns (`st_y` / `st_x`).
- Uploads send `lat` / `lng`; the service builds the point (`ST_SetSRID(ST_MakePoint(lng, lat), 4326)`).
- Spatial queries (nearest apiary, etc.) run server-side only.

### 4.4 Migration rules

- One concern per migration file; name it descriptively (`20261119120000_create_colonies.sql`).
- Every `create table` migration includes in the same file: RLS enable, policies, `owner_id` index, `updated_at` trigger.
- Never edit a migration that has been pushed to the hosted project — write a new one.
- Keep `seed.sql` for local development only; no real user data.
- After a migration: update the SQLAlchemy model, the sync rules, and notify the frontend schema.

---

## 5. Security & authorization

### 5.1 JWT verification (`app/auth/jwt.py`)

- Read `Authorization: Bearer <token>`.
- Verify with Supabase **JWKS** (`{SUPABASE_URL}/auth/v1/.well-known/jwks.json`), cached; fall back to `SUPABASE_JWT_SECRET` (HS256) only if the project uses legacy symmetric keys.
- Check `exp`, `aud == "authenticated"`, `iss == {SUPABASE_URL}/auth/v1`.
- Return a `CurrentUser(id=sub, email, role)` object. Reject anything else with `401`.

### 5.2 Row Level Security

- RLS **enabled on every table**. Base policy for user tables:
  `using (owner_id = auth.uid()) with check (owner_id = auth.uid())`.
- Child tables (e.g. `treatments.colony_id`) also need a check that the referenced colony belongs to the same owner (policy or trigger) — no cross-user references.

### 5.3 FastAPI DB access = defense in depth

FastAPI connects with a DB role that *could* bypass RLS, so every request runs in a transaction that **drops privileges**:

```sql
set local role authenticated;
select set_config('request.jwt.claims', '{"sub":"<user_id>","role":"authenticated"}', true);
```

This happens in `db.user_session(user)`. On top of that, services always filter by `owner_id` explicitly. **Both** layers, always. The only code allowed to run without user claims is clearly-named admin/maintenance code (none planned yet).

### 5.4 Secrets

- Env vars only, read via `app/config.py` (pydantic-settings). `.env.example` lists them all without values.
- Required: `DATABASE_URL`, `SUPABASE_URL`, `SUPABASE_JWKS_URL` or `SUPABASE_JWT_SECRET`, `ANTHROPIC_API_KEY`. Optional: `LANGSMITH_API_KEY`, `LANGSMITH_PROJECT`, `ANTHROPIC_MODEL`, `LOG_LEVEL`, `CORS_ORIGINS`.
- **The Anthropic key never leaves the server.** The app never talks to the LLM directly.
- Never log tokens, full transcripts at INFO level, or audio paths with signed URLs.

### 5.5 Storage

- Buckets `photos` and `voice` are **private**.
- Object path: `{user_id}/{record_or_note_id}/{filename}`; Storage RLS policies check the first path segment equals `auth.uid()`.
- The app uploads directly with supabase-js; the DB only stores `storage_path`.

---

## 6. Sync design (the most important backend contract)

### 6.1 Downstream — PowerSync sync rules

`backend/powersync/sync-rules.yaml` defines one bucket per user, parameterized by `token_parameters.user_id`. Each user's devices receive **only their own rows**, including soft-deleted ones (so devices learn about deletions), e.g.:

```yaml
bucket_definitions:
  user_data:
    parameters: SELECT request.user_id() AS user_id
    data:
      - SELECT * FROM colonies WHERE owner_id = bucket.user_id
      - SELECT id, owner_id, name, kind, notes, st_y(location) AS lat, st_x(location) AS lng,
               created_at, updated_at, client_updated_at, deleted_at
        FROM apiaries WHERE owner_id = bucket.user_id
      # ... one line per synced table
```

(Exact syntax must match the PowerSync version in use — verify against its docs when writing it.)

**Do not sync:** `sync_conflicts` raw payloads (sync a summary only if the app needs to show them), LangGraph checkpoint tables, anything belonging to other users.

### 6.2 Upstream — `POST /v1/sync/upload`

The PowerSync upload handler on the device sends its queued CRUD operations in batches:

```jsonc
// request
{
  "ops": [
    { "op": "PUT",    "table": "treatments", "id": "uuid", "data": { ... full row ... } },
    { "op": "PATCH",  "table": "colonies",   "id": "uuid", "data": { ... changed fields ... } },
    { "op": "DELETE", "table": "harvests",   "id": "uuid" }
  ]
}
// response
{
  "results": [
    { "id": "uuid", "status": "applied" },
    { "id": "uuid", "status": "conflict", "conflict_id": "uuid" },
    { "id": "uuid", "status": "rejected", "error": "amount must be > 0" }
  ]
}
```

Rules:

1. **Whitelist tables and columns.** Unknown tables/columns are rejected. `owner_id`, `created_at`, `updated_at` from the client are ignored and set server-side.
2. **Idempotent upsert by `id`.** `PUT` = `insert ... on conflict (id) do update`. Replaying the same batch is a no-op — a retried harvest is never counted twice.
3. **Last-write-wins on `client_updated_at`.** If the incoming `client_updated_at` is older than the stored one, do not overwrite: keep the newer row and write a `sync_conflicts` row ("latest edit wins, conflict flagged for review").
4. **`DELETE` = soft delete** (`deleted_at = now()`).
5. **Route each op through the domain service** (`services/treatments.py`, etc.) so the same validation applies as for voice entries. `upsert.py` provides the generic mechanics.
6. **Never jam the queue.** A *permanently* invalid op (validation error) is returned as `rejected`, logged, and the request still returns `200` so the device can complete the batch. Only *transient* failures (DB down, 5xx) return an error so the device retries. The frontend must surface rejected ops to the user.
7. **One transaction per batch** where possible; if one op fails validation, the others still apply (use savepoints per op).
8. **Ordering matters:** apply ops in the order received (a colony must exist before its placement).

### 6.3 Placements / moves

- A move is a single service call: `colonies.move(colony_id, to_apiary_id, moved_at)` → closes the open placement (`ended_at = moved_at`) and opens a new one. Offline, the device does the same two writes locally; the server validates the invariant "one open placement per colony" and resolves overlaps by `client_updated_at`.
- `stationary` colonies may still be moved (a move just turns it into a historical fact); the mode is informational for UI.

### 6.4 Inventory side effects

- A treatment with an `inventory_item_id` produces an `inventory_adjustments` row (`reason = used`, `delta = -amount`, `treatment_id` set).
- The **device creates it** in the same local transaction (so stock is correct offline); the server validates consistency but does not create a second one (idempotent on `treatment_id`).

---

## 7. API conventions

- All routes under `/v1/`. Health check at `/health` (no auth).
- JSON in/out, `snake_case` field names, ISO-8601 UTC timestamps, UUID strings.
- Every endpoint has a Pydantic request model and response model; OpenAPI at `/docs` is the contract the frontend uses.
- Errors: `{"error": {"code": "string_code", "message": "human text", "details": {...}}}` with proper HTTP status (400 validation, 401 auth, 403 forbidden, 404 not found / not owned, 409 conflict, 422 Pydantic, 5xx server).
- **404, not 403,** when a user requests another user's resource (don't leak existence).
- Routers are thin (≈10–20 lines). Logic → services.
- Async everywhere; no blocking calls (no `requests`, no sync DB driver) in request paths.
- CORS: not needed for the native app; keep it closed except for local tools.

### Planned endpoints

| Method & path | Purpose | Phase |
| --- | --- | --- |
| `GET /health` | Liveness | 1 |
| `GET /v1/me` | Verify token, return user/profile | 1 |
| `POST /v1/sync/upload` | PowerSync upload queue | 1–3 |
| `GET /v1/colonies/{id}/history` | Merged placements + records timeline (if too heavy for local SQLite) | 1–2 |
| `GET /v1/apiaries/nearby?lat&lng&radius` | PostGIS query (optional) | later |
| `GET /v1/conflicts` / `POST /v1/conflicts/{id}/resolve` | Conflict review | 3 |
| `POST /v1/voice/sessions` | Start a voice entry | 4 |
| `POST /v1/voice/sessions/{thread_id}/reply` | Answer a question / confirm | 4 |
| `POST /v1/voice/notes/{voice_note_id}/process` | Process an offline pending voice note | 4 |
| `POST /v1/assistant/ask` | Spoken history questions | 5 |

---

## 8. Voice assistant (LangGraph)

### 8.1 Graph

```text
transcript ──► extract ──► resolve ──► missing info? ──yes──► ask (interrupt) ──┐
                 ▲                          │no                                  │
                 └──────────────────────────┼────────── user's answer ◄──────────┘
                                            ▼
                                   confirm (interrupt) ──"yes"──► save record
                                            │"no" / correction
                                            └──► back to extract
```

| Node | What it does | LLM? |
| --- | --- | --- |
| `extract` | Transcript (+ previous draft + answer) → typed draft via structured output: `TreatmentDraft`, `HarvestDraft`, `InventoryDraft`, `NoteDraft` (a discriminated union). | **Yes** |
| `resolve` | Plain code: "hive 12" → colony id (by `number` / `label`, scoped to user and context apiary), product → inventory item (fuzzy match), units normalization, date defaults ("today"). Unknown/ambiguous → list of missing fields. | No |
| `ask` | `interrupt()` with one question (one field at a time, short, speakable). | No (templated) |
| `confirm` | `interrupt()` with a spoken summary. **Always reads back amounts and units.** | No (templated) |
| `save` | Calls the **same service** as typed entries (`services.treatments.create(...)`). Record `id` is generated once and stored in the graph state so a retried save is idempotent. `source = 'voice'`. | No |

### 8.2 Rules

- **The LLM never decides IDs, never writes to the DB, never sees other users' data.** It only gets the transcript, the current draft, and a short list of the user's colony labels/product names as hints.
- Structured output only (Pydantic models with `with_structured_output`). Validate; on parse failure → "not understood" response, not a crash.
- Confirmation words ("yes", "da", "correct", "no", "change the amount to…") are interpreted by a small classifier step (LLM or rules) — "no"/corrections go back to `extract` with the correction appended.
- Conversation state persists via **`AsyncPostgresSaver`** (langgraph-checkpoint-postgres); `thread_id` is a UUID returned to the app. A question and its answer can arrive in separate HTTP requests (even minutes apart).
- Threads are scoped to the user: store `owner_id` in state and verify it on every resume.
- Prompts live in `assistant/prompts/` as versioned templates, not inline strings.
- Locale-aware: pass the user's `locale` so questions/summaries are produced in their language.
- Model name from config (`ANTHROPIC_MODEL`, default Haiku). Set timeouts and a max retry count.

### 8.3 Voice API contract

```jsonc
// POST /v1/voice/sessions
{ "transcript": "Hive 12, oxalic acid, 5 ml, queen seen, calm",
  "context": { "colony_id": "uuid|null", "apiary_id": "uuid|null" },
  "locale": "en-US", "voice_note_id": "uuid|null", "client_time": "ISO" }

// POST /v1/voice/sessions/{thread_id}/reply
{ "text": "yes" }

// Response (both)
{ "thread_id": "uuid",
  "status": "question" | "confirm" | "saved" | "not_understood" | "cancelled",
  "speak": "Treatment for Hive 12: oxalic acid, 5 millilitres, today. Save?",
  "haptic": "needs_answer" | "saved" | "not_understood",
  "draft": { ... current typed draft ... },
  "record": { "table": "treatments", "id": "uuid" } | null }
```

The app speaks `speak`, plays `haptic`, and listens again if status is `question` / `confirm`. The saved record reaches the device via PowerSync; `record` lets the app show it immediately.

### 8.4 Offline voice notes

When offline, the device saves a `voice_notes` row (`status = pending`). After reconnect it syncs up; the app calls `/v1/voice/notes/{id}/process`, which starts a session with that transcript and the stored context. Confirmation still happens with the user — **never auto-save a voice note without confirmation.**

---

## 9. Coding conventions (Python)

- Python 3.12+, full type hints, `from __future__ import annotations` not needed.
- Formatting/linting: **ruff** (format + lint). Type check: **mypy** or **pyright** (strict on `services/` and `assistant/`).
- Naming: modules `snake_case`, classes `PascalCase`, Pydantic schemas suffixed by role: `TreatmentCreate`, `TreatmentOut`, `TreatmentDraft`.
- Dependency injection via FastAPI `Depends` (`get_current_user`, `get_db`).
- Services are plain async functions taking `(session, user, payload)` and returning domain objects/schemas — easy to test without HTTP.
- Logging: stdlib `logging` with structured fields (`user_id`, `request_id`, `thread_id`); no `print`.
- Time: always timezone-aware (`datetime.now(UTC)`); never naive datetimes.
- No business constants scattered around — units, enums, limits in one module (`models/schemas/enums.py`) mirroring DB enums.

---

## 10. Testing

| Layer | How |
| --- | --- |
| Services | pytest + pytest-asyncio against the **local Supabase Postgres** (`supabase start`) in a transaction rolled back per test. |
| RLS | SQL tests (or pytest) proving user A cannot read/write user B's rows. Required for every new table. |
| Sync upload | Replay the same batch twice → one row. Older `client_updated_at` → conflict row, server data kept. Invalid op → `rejected`, others applied. |
| API | `httpx.AsyncClient` with a forged test JWT (test signing key). |
| Assistant | Fake LLM returning fixed structured outputs; test graph paths: happy path, missing amount → ask → answer, "no" → correction, ambiguous hive, not understood. Optional small eval set of real transcripts (e.g. "15" vs "50"). |

Rule: **no new service function without a test**; no new table without an RLS test.

How to run:
- `uv run pytest` — unit tests only (no database).
- `uv run pytest --db` — also runs `tests/db/` against `DATABASE_URL`. It creates throwaway `b4y-test-*@example.com` users in `auth.users` and deletes them (and, by cascade, all their rows) afterwards. Takes ~2 minutes over the pooler.

---

## 11. Local development, deployment & environments

**Default setup: hosted Supabase, no Docker.** Docker is only needed to run Supabase on your own machine (`supabase start`); it's optional.

1. Create a hosted Supabase project (dev). Install the Supabase CLI (`npm i -g supabase` or `npx supabase`).
2. Once: `npx supabase login`. Then `cd backend && npx supabase link --project-ref <ref>` and `npx supabase db push --remote` — applies `supabase/migrations/` to the hosted project. (CLI 3.x targets the local Docker stack unless you pass `--remote`.)
3. `cp .env.example .env`, fill in values. `uv sync` then `uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`.
   Use `0.0.0.0` so a physical phone on the same network can reach it via the computer's LAN IP.
4. `uv run pytest`, `uv run ruff check .`, `uv run mypy app` must pass before committing.
5. PowerSync: hosted instance pointed at the Supabase DB (publication `powersync`), Supabase Auth as JWT source, rules from `powersync/sync-rules.yaml`.
6. Free-tier Supabase projects pause after ~1 week idle.

Optional local stack: install Docker, `npx supabase start`, `npx supabase db reset`.

**Deployment: Vercel.** FastAPI runs as a Vercel Python serverless function (project Root Directory = `backend`, entrypoint `app/main.py:app`). Because functions are short-lived:
- `DATABASE_URL` = Supabase **pooler** URL (port 6543, transaction mode) and `DB_SERVERLESS=true` → `NullPool`, prepared statements off (see `app/db.py`).
- Keep requests short. The voice assistant (phase 4) must fit Vercel's function time limit; LangGraph state lives in Postgres, so each request is independent.
- Env vars are set in the Vercel project settings, never committed.

Environments: `dev` (hosted Supabase + Vercel preview), `prod` (later). Config differs only by env vars.

---

## 12. Roadmap — what the backend delivers per phase

| Phase | Backend deliverables | Done when |
| --- | --- | --- |
| **1 · Apiaries & colonies** | Supabase project, migrations for `profiles`, `apiaries`, `colonies`, `colony_placements` + RLS; JWT verification; `/health`, `/v1/me`; sync rules for those tables; `sync/upload` for them; move service | A colony moved between sites shows both placements in its history. |
| **2 · Field records** | Migrations + services for `treatments`, `harvests`, `inventory_items`, `inventory_adjustments`, `colony_notes`; sync rules; upload support | A treatment recorded from a colony screen lands correctly with colony + apiary. |
| **3 · Offline field testing** | Hardened upsert (idempotency, LWW, savepoints), `sync_conflicts` + review endpoints, rejected-op reporting | Harvest in airplane mode → restart → reconnect → **exactly one** server row. |
| **4 · Voice assistant** | LangGraph graph, checkpointer, voice endpoints, `voice_notes` processing, prompts, tests | Treatment said with missing amount → one follow-up → confirm → correct record. |
| **5 · Assistant extras** | History Q&A ("what did I do to hive 12 last month?") as read-only tools; treatment reminders | Correct date and product read back for a colony's last treatment. |
| **Later** | Photo analysis (frames, varroa counts) | TBD |

**Do not build ahead of the phase** unless it's cheap and doesn't lock decisions (e.g. adding `source` column early is fine; building the voice graph in phase 1 is not).

---

## 13. Out of scope (for now)

- A web dashboard (Supabase dashboard covers review during development).
- Always-listening wake word.
- Multi-user / shared apiaries (teams). Schema uses `owner_id` everywhere; sharing would be a deliberate future migration.
- Direct table writes from the app via supabase-js / PostgREST.
- Server-generated IDs for client records.

---

## 14. Decision log

Add a line whenever a rule above changes or a non-obvious choice is made.

| Date | Decision | Why |
| --- | --- | --- |
| 2026-11-19 | Project split into `frontend/` and `backend/` (README proposed `apps/mobile`); `supabase/` and `powersync/` live under `backend/`. | Clear ownership; each side has its own architect doc. |
| 2026-11-19 | Writes go up through FastAPI (`/v1/sync/upload`), reads come down through PowerSync. | README sync flow; one validation path for typed and voice entries. |
| 2026-11-19 | Soft deletes + client-generated UUIDs + LWW on `client_updated_at` with conflict log. | Offline-first sync needs tombstones and idempotent retries. |
| 2026-11-19 | FastAPI runs queries with `set local role authenticated` + JWT claims (RLS applies) *and* explicit `owner_id` filters. | Defense in depth. |
| 2026-11-19 | Apiary location synced as `lat`/`lng`, stored as PostGIS `geography`. | SQLite has no PostGIS. |
| 2026-11-19 | Deploy FastAPI on Vercel; develop against hosted Supabase (Docker optional). | User's choice; no Docker needed. Requires pooler URL + `DB_SERVERLESS=true`. |
| 2026-11-19 | Enum-like columns are `text` + `check` constraints, not Postgres enums. | Easier to evolve via migrations; maps 1:1 to SQLite text. |
| 2026-11-19 | Server resolves overlapping open placements (`services/colonies.py`): a later placement wins; server-side closes bump `client_updated_at` to now. | Two offline devices can move the same colony. |
| 2026-11-19 | `sync_conflicts` ids are server-generated; the table is not synced to devices yet. | Written by the API, not by devices. |
| 2026-11-19 | LangChain/LangGraph deps are added in phase 4, not now. | Don't build ahead of the phase; keeps the serverless bundle small. |
| 2026-11-19 | `profiles.default_units` dropped for now. | Not needed until phase 2 forms; add with a migration then. |
