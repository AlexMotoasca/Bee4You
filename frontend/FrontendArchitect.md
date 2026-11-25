# Frontend Architect — Bee4You

> **Purpose of this file.** This is the single source of truth for how the Bee4You mobile app is built.
> Before (and after) every frontend prompt, check the change against this document.
> If a change needs to break a rule here, **update this file first** (and add a line to the Decision Log at the bottom) — never let the code and this file drift apart.
> The backend counterpart is `backend/BackendArchitect.md`. Shared contracts (tables, units, API shapes) must match it. **The backend is live** — section 4.0 is the data contract the app must follow.

---

## 0. Quick checklist for every frontend prompt

- [ ] **Works offline.** Any field action (create/edit a colony, treatment, harvest, inventory, note, move) writes to **local SQLite via PowerSync** and succeeds with no network.
- [ ] **Never call the API or supabase-js to write records.** Writes go to the local DB; the PowerSync connector uploads them. (supabase-js = Auth + Storage only; API client = upload connector + voice.)
- [ ] **New records get a client-generated UUID** and set `client_updated_at` on every edit.
- [ ] **Deletes are soft** (`deleted_at = now`); every query filters `deleted_at IS NULL`.
- [ ] **Reads come from local SQLite** (`useQuery` reactive queries), not from network fetches.
- [ ] **Values match the data contract (§4.0):** column names, allowed values (units, statuses, kinds), length/amount limits. The server rejects anything else.
- [ ] **New table/column?** It must exist in the backend migration + Sync Streams first; then update `src/db/schema.ts`. Names identical to the backend.
- [ ] **Glove-friendly UI:** touch targets ≥ 56 dp, primary action reachable one-handed, high contrast for sunlight, no tiny icons-only controls for important actions.
- [ ] **"Saved" ≠ "synced".** Show local save (haptic + toast) separately from sync status.
- [ ] **Contextual quick entry:** if the user is on a colony/apiary screen, that colony/apiary is pre-selected.
- [ ] **Voice entry produces the same record** a typed entry would — no voice-only data shapes.
- [ ] **Romanian and English** for everything the user reads or hears (`locale` `ro-RO` / `en-US`).
- [ ] **No secrets in the app.** Only `EXPO_PUBLIC_*` values (URLs, publishable key, map key restricted to the app). Never the Groq key.
- [ ] **TypeScript strict, no `any`** in domain code.
- [ ] Change belongs to the **current roadmap phase** (section 13).

---

## 1. What the frontend is

Bee4You is a **mobile field notebook** for beekeepers with permanent or migratory apiaries. The user picks a colony, logs work at the hive, and puts the phone away — **even without signal**. Hands are gloved and sticky, so entries can also be made **by voice** (push-to-talk → assistant fills the form → reads it back → vibrates on save), in **Romanian or English**.

The app is **offline-first**: the local SQLite database (PowerSync) is the source of truth for the UI. The network is only needed for sign-in, the first download, syncing, and the voice assistant.

```text
Mobile app (Android / iOS) — React Native + Expo (development build)
  ├── SQLite via PowerSync     → all records, offline upload queue      ◄── PowerSync Cloud (Sync Streams)
  ├── MapLibre + OSM tiles     → apiary map, offline map regions
  ├── Speech / TTS / haptics   → voice entry (on-device, works offline)
  ├── supabase-js              → sign-in, session refresh                ──► Supabase Auth
  └── API client (FastAPI)     → upload queue, voice assistant           ──► https://bee4you-backend.vercel.app
```

---

## 2. Technology stack (fixed — do not swap without a Decision Log entry)

| Technology | Role | Rules |
| --- | --- | --- |
| React Native + TypeScript + **Expo (development build)** | Android & iOS from one codebase | Expo Go is **not** supported (native modules for maps & speech). Use `npx expo install` for native deps. |
| **Expo Router** | File-based navigation | Screens in `src/app/`. Keep screen files thin. |
| **StyleSheet + tokens** (NativeWind deferred, see Decision Log) | Styling | Use `src/theme/tokens.ts` and the primitives in `src/components/ui.tsx`; no ad-hoc hex colors in components. |
| **@maplibre/maplibre-react-native** | Map, apiary markers, offline regions | Vector tiles from MapTiler/Stadia. **Never** `tile.openstreetmap.org`. |
| **MapTiler or Stadia Maps** | Tile hosting + geocoding | Key restricted to the app bundle id. |
| **@powersync/react-native** (+ `@powersync/react`) | Local SQLite, reactive queries, upload queue | The only data layer for records. Use an SDK version that supports **Sync Streams** (the backend uses `edition: 3`). |
| **@supabase/supabase-js** | Auth, session refresh | **No table reads/writes** through it. |
| **expo-speech-recognition** | Speech → text, on-device where supported | Push-to-talk only. `lang` = profile locale (`ro-RO` / `en-US`). |
| **expo-speech** | Text → speech (offline) | Reads questions & confirmations; same locale. |
| **expo-haptics** | Vibration patterns | Exactly three semantic patterns (section 9.4). |

Proposed helpers (not in the README; adopt or replace, then record in the Decision Log):

| Helper | Role |
| --- | --- |
| `react-hook-form` + `zod` | Forms + validation; zod schemas mirror §4.0 limits and are shared by typed and voice-draft forms |
| `zustand` | Small ephemeral UI state (voice session state, map camera). Not for records. |
| `expo-secure-store` | Persist Supabase session securely |
| `date-fns` | Date formatting/parsing (with `ro` and `en` locales) |
| `expo-crypto.randomUUID()` | Client-generated IDs |
| `openapi-typescript` | Generate API types from `https://bee4you-backend.vercel.app/openapi.json` |

---

## 3. Folder layout

Everything frontend-related lives under `frontend/`:

```text
frontend/
├── FrontendArchitect.md         # ← this file
├── app.config.ts                # Expo config (plugins: maplibre, speech recognition, permissions)
├── package.json / lockfile      # commit the lockfile
├── tailwind.config.js           # NativeWind tokens (colors, sizes)
├── .env.example                 # EXPO_PUBLIC_* only
└── src/
    ├── app/                     # Expo Router — screens & layouts ONLY (thin)
    │   ├── _layout.tsx          # providers: PowerSync, Auth, theme, i18n
    │   ├── (auth)/sign-in.tsx
    │   └── (main)/
    │       ├── _layout.tsx      # tabs: Map · Apiaries · Inventory · Settings
    │       ├── map.tsx
    │       ├── apiaries/index.tsx
    │       ├── apiaries/[apiaryId].tsx
    │       ├── colonies/[colonyId].tsx          # colony history timeline
    │       ├── colonies/[colonyId]/move.tsx
    │       ├── entry/treatment.tsx              # ?colonyId=&apiaryId= prefill
    │       ├── entry/harvest.tsx
    │       ├── entry/inventory.tsx
    │       ├── entry/note.tsx
    │       ├── voice.tsx                        # push-to-talk session (modal)
    │       ├── sync.tsx                         # sync status, rejected ops, pending voice notes
    │       └── settings/index.tsx               # language, offline maps, offline voice check, sign out
    ├── features/                # domain modules: components + hooks + queries + mutations
    │   ├── apiaries/
    │   ├── colonies/            # incl. placements & moves
    │   ├── treatments/
    │   ├── harvests/
    │   ├── inventory/
    │   ├── notes/
    │   └── sync/                # status indicator, rejected ops list
    ├── voice/                   # push-to-talk, recognizer, TTS, haptics, voice API calls, session state machine, phrases (ro/en)
    ├── i18n/                    # UI strings: ro.ts, en.ts
    ├── db/
    │   ├── schema.ts            # PowerSync schema — mirrors §4.0
    │   ├── powersync.ts         # database instance
    │   ├── connector.ts         # fetchCredentials (Supabase token) + uploadData (→ FastAPI)
    │   └── queries/             # shared SQL helpers
    ├── lib/
    │   ├── supabase.ts          # supabase client (auth)
    │   ├── api.ts               # typed FastAPI client (types generated from OpenAPI)
    │   ├── map.ts               # style URL, offline region helpers
    │   ├── ids.ts               # newId(), nowIso()
    │   ├── units.ts             # unit enum + formatting (ro/en)
    │   └── env.ts               # validated EXPO_PUBLIC_* config
    ├── components/              # generic UI: BigButton, Field, NumberPad, SyncBadge, EmptyState
    └── theme/                   # tokens, typography
```

**Layering rule:** `app/` (screens) → `features/*` (hooks, components) → `db/` & `lib/`. Screens never write SQL directly; they call feature hooks (`useColony`, `useCreateTreatment`). `voice/` never writes records itself: the server saves voice entries and they arrive through PowerSync.

---

## 4. Data layer (PowerSync) — the core of the app

### 4.0 Data contract (what the backend accepts and sends)

Every synced table has these **common columns**:

| Column | Notes |
| --- | --- |
| `id` | UUID text, **generated on the phone** (`expo-crypto.randomUUID()`). |
| `owner_id` | Current user id. Set it locally for queries; the server ignores what the phone sends and uses the login. |
| `created_at`, `updated_at` | Server-managed. Write `now` locally for display; the server ignores them. |
| `client_updated_at` | **Required on every write.** Phone time of the last edit; the newer edit wins (§4.4). |
| `deleted_at` | Null, or the soft-delete time. |

Tables (allowed values are the **only** values the server accepts):

| Table | Columns (besides the common ones) | Phone may |
| --- | --- | --- |
| `profiles` | `display_name` (≤ 100), `locale` (`ro-RO` / `en-US`, 2–20 chars). Row `id` = user id, created at sign-up. | PUT / PATCH **own row only**, no delete |
| `apiaries` | `name` (1–120), `kind` `permanent`/`temporary`, `lat` (−90..90), `lng` (−180..180) — **both or neither**, `notes` (≤ 2000) | PUT / PATCH / DELETE |
| `colonies` | `label` (1–60, e.g. "Stup 12"), `number` (int ≥ 0, optional — used by voice: "stupul 12"), `mode` `stationary`/`migratory`, `status` `active`/`dead`/`sold`/`merged`, `queen_year` (1990–2100), `notes` | PUT / PATCH / DELETE |
| `colony_placements` | `colony_id`, `apiary_id`, `started_at`, `ended_at` (null = colony is there now; ≥ `started_at`) | PUT / PATCH / DELETE |
| `inventory_items` | `name` (1–120), `category` `treatment`/`equipment`/`consumable`/`other`, `unit`, `apiary_id` (null = home/store), `notes` | PUT / PATCH / DELETE |
| `inventory_adjustments` | `item_id`, `delta` (≠ 0; + added, − used), `unit`, `reason` `purchase`/`used`/`moved`/`correction`, `apiary_id`, `adjusted_at`, `treatment_id` (set when a treatment used stock), `notes`, `source` | PUT / PATCH / DELETE |
| `treatments` | `colony_id`, `apiary_id` (where it happened), `inventory_item_id` (optional), `product_name` (1–120), `amount` (> 0), `unit`, `treated_at`, `notes`, `source` | PUT / PATCH / DELETE |
| `harvests` | `apiary_id`, `colony_id` (optional), `quantity` (> 0), `unit`, `harvested_at`, `notes`, `source` | PUT / PATCH / DELETE |
| `colony_notes` | `colony_id`, `apiary_id`, `noted_at`, `queen_seen` (bool, optional), `temperament` `calm`/`nervous`/`aggressive` (optional), `text` (≤ 4000) — **at least one of the three** | PUT / PATCH / DELETE |
| `voice_notes` | `transcript` (**1–4000, required**), `audio_path`, `locale`, `context_colony_id`, `context_apiary_id`, `status` `pending`/`processing`/`needs_answer`/`needs_confirmation`/`saved`/`cancelled`/`failed`, `thread_id`, `result_record_type`, `result_record_id`, `error` | PUT (create as `pending`); the **server** updates status/result fields |

- **Units** (everywhere): `ml`, `l`, `g`, `kg`, `pcs`, `strips`, `frames`.
- **Amounts** (`amount`, `quantity`, `delta`): > 0 (delta ≠ 0), at most 1,000,000, at most 4 decimals.
- **`source`**: `manual` for typed entries, `voice` is set by the server.
- Referenced rows (`colony_id`, `apiary_id`, `item_id`, …) must be the user's own and must be uploaded **before** the rows that reference them (same transaction order is fine).
- Not synced to the phone: `voice_sessions`, `sync_conflicts` (server-only).

### 4.1 Schema mirrors the backend

`src/db/schema.ts` declares the tables and columns of §4.0, as **PowerSync delivers them**:

- `apiaries` has `lat` / `lng` (REAL); the server stores a PostGIS point.
- UUIDs `TEXT`; timestamps `TEXT` like `2026-11-25 09:30:00.000Z`; `numeric` amounts `TEXT` (exact, e.g. `"5.5"` — parse for display, never do float math on stock); integers `INTEGER`; booleans `INTEGER` 0/1. Convert in the feature layer, not in components.
- New rows may be written with ISO `T` timestamps (`new Date().toISOString()`); the server accepts both formats.

PowerSync uses one **auto-subscribed** Sync Stream (`user_data`) containing all of the user's rows, so the app only calls `db.connect(connector)` — no subscription code.

**Order of change:** backend migration → Sync Streams → `schema.ts` → features. Never add a local-only column the backend doesn't know about (except PowerSync `localOnly` tables, which must be documented here).

### 4.2 Writing records

Every mutation hook follows this pattern:

```ts
const id = newId();                     // client UUID
const now = nowIso();
await db.writeTransaction(async (tx) => {
  await tx.execute(
    `INSERT INTO treatments (id, owner_id, colony_id, apiary_id, inventory_item_id, product_name,
       amount, unit, treated_at, notes, source, created_at, updated_at, client_updated_at)
     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'manual', ?, ?, ?)`,
    [id, userId, colonyId, apiaryId, itemId, productName, amount, unit, treatedAt, notes, now, now, now]
  );
  if (itemId && item.unit === unit) {
    // Stock goes down in the SAME transaction; units are never converted.
    await tx.execute(
      `INSERT INTO inventory_adjustments (id, owner_id, item_id, delta, unit, reason, apiary_id,
         adjusted_at, treatment_id, source, created_at, updated_at, client_updated_at)
       VALUES (?, ?, ?, ?, ?, 'used', ?, ?, ?, 'manual', ?, ?, ?)`,
      [newId(), userId, itemId, `-${amount}`, unit, apiaryId, treatedAt, id, now, now, now]
    );
  }
});
haptics.saved();                        // local save confirmed
```

Rules:

- **Related writes in one `writeTransaction`**, parents first.
  - **Move a colony** = `UPDATE colony_placements SET ended_at = :movedAt` on the open placement + `INSERT` a new placement (`started_at = :movedAt`, `ended_at = NULL`). If two phones moved the same colony offline, the server sorts it out by date.
  - **Treatment from stock** = treatment + `used` adjustment (only when units match).
- **Update** = set changed fields + `client_updated_at = now`.
- **Delete** = `UPDATE ... SET deleted_at = now, client_updated_at = now`.
- Validate with the feature's zod schema (§4.0 limits) **before** writing.
- Keep amounts as decimal strings (`"5"`, `"2.5"`), not floats.

### 4.3 Reading records

- Use reactive `useQuery` from `@powersync/react` inside feature hooks; screens re-render automatically when sync brings new data.
- Always `WHERE deleted_at IS NULL`.
- **Colony history** = union of placements + treatments + harvests + notes for that colony, sorted by event date, each showing the **apiary where it happened** (from the record's own `apiary_id`, not the colony's current apiary).
- **Current apiary of a colony** = placement with `ended_at IS NULL`.
- **Inventory stock** = sum of `delta` per item (and per apiary if needed), computed with decimals, not floats.

### 4.4 Upload connector (`src/db/connector.ts`)

- `fetchCredentials()` → `{ endpoint: EXPO_PUBLIC_POWERSYNC_URL, token: <Supabase access token> }` (refresh the session if it is about to expire).
- `uploadData()` → read the CRUD batch (≤ 1000 ops), send:

```jsonc
// POST https://bee4you-backend.vercel.app/v1/sync/upload   Authorization: Bearer <supabase token>
{ "ops": [
  { "op": "PUT",    "table": "treatments", "id": "uuid", "data": { /* full row (opData) */ } },
  { "op": "PATCH",  "table": "colonies",   "id": "uuid", "data": { /* changed columns + client_updated_at */ } },
  { "op": "DELETE", "table": "harvests",   "id": "uuid" }
]}
// 200
{ "results": [
  { "id": "uuid", "table": "treatments", "status": "applied" },
  { "id": "uuid", "table": "colonies",   "status": "conflict", "conflict_id": "uuid" },
  { "id": "uuid", "table": "harvests",   "status": "rejected", "error": "amount: Input should be greater than 0" }
]}
```

| Response | Meaning | Connector does |
| --- | --- | --- |
| 200, all `applied` | Saved on the server | `transaction.complete()` |
| 200 with `conflict` | Another device's newer edit won; logged on the server | `complete()`. The newer version arrives through sync. |
| 200 with `rejected` | The row can never be saved (invalid data) | `complete()`, and **store the op + error locally** for the Sync screen. After the next sync the row reverts/disappears on the phone, so the Sync screen is the only place the user can see and re-enter it. |
| 401 | Login expired | Refresh the Supabase session, then **throw** (PowerSync retries) |
| 5xx / network error / timeout | Temporary | **Throw** — PowerSync retries; every op is idempotent |
| other 4xx (400/413/422) | Bug in the request shape | Store the batch for the Sync screen, `complete()`, log it — never jam the queue |

---

## 5. Auth

- Supabase Auth (email now; Google/Apple later). Use the project's **publishable key**. Session persisted with `expo-secure-store`; `autoRefreshToken: true`.
- The same access token is used by PowerSync (verified via Supabase JWKS) and the API.
- On first sign-in **online**: connect PowerSync → initial download. Show a clear "Se descarcă stupinele…" / "Downloading your apiaries…" state.
- Subsequent launches work **offline** with the cached session and local DB.
- Expired session while offline: keep the app usable locally; uploads pause; prompt for sign-in when back online (in the sync badge, not a blocking modal in the field).
- Sign-out: warn if there are **unsynced changes** (they would be lost), then disconnect and clear the local DB.

---

## 6. Navigation & screens

| Screen | Purpose | Key actions |
| --- | --- | --- |
| Map | MapLibre map with apiary pins | Tap pin → apiary; add apiary at location; current location |
| Apiaries list | Searchable list of saved apiaries — **always works offline**, even without map tiles | Open apiary, add apiary |
| Apiary | Colonies currently placed here, recent harvests | Open colony, **log harvest**, **adjust inventory**, add colony |
| Colony | Header (label, number, mode, status, current apiary) + history timeline | **Quick entry**: treatment / note / move; voice button |
| Move colony | Choose destination apiary + move date | Writes placement close/open |
| Entry forms | Treatment, harvest, inventory, note — prefilled from context | Save (big button) |
| Voice | Push-to-talk session overlay | Hold to talk, see draft, hear questions/confirmation |
| Sync | Sync status, pending count, rejected ops, **pending voice notes to confirm** | Retry, re-enter rejected, process voice notes |
| Settings | Language (`ro-RO` / `en-US`, speech + UI), offline map regions, offline voice availability, account | Download region, sign out |

**Contextual quick entry is a core feature:** `entry/treatment?colonyId=X&apiaryId=Y` pre-selects both; the user should never reselect the colony they're standing at. (Phase 2 completion check.)

Hives should get a `number`: voice matches "stupul 12" by number first, then by label.

---

## 7. Field UX rules (gloves, sun, bees)

- Touch targets **≥ 56 dp**; primary "Save" button full-width at the bottom, reachable with a thumb.
- Large fonts for key values (amounts, hive labels); high-contrast theme readable in direct sunlight. Support dark mode, but test light mode outdoors.
- Prefer **steppers, chips, and big number pads** over free-text keyboards. Recent products / last-used amount as one-tap chips.
- Minimal required fields; sensible defaults (date = now, unit = the item's unit / last used for that product).
- Every save gives **immediate feedback**: haptic + short toast, then navigate back.
- No destructive action without confirmation; prefer undo toasts for deletes.
- Never show a spinner that blocks a field action waiting for the network.
- Sync status always visible but unobtrusive (badge: ✓ synced / ↑ N pending / ⚠ attention).
- Romanian formatting in `ro-RO`: decimal comma ("2,5 l"), Romanian dates.

---

## 8. Maps

- Style URL from MapTiler or Stadia (`lib/map.ts`), key from `EXPO_PUBLIC_MAP_STYLE_URL`, restricted to the app.
- **Never use `tile.openstreetmap.org`** (usage policy forbids app traffic). Show OSM attribution as required by the provider.
- Offline regions: Settings → "Download area around my apiaries" (bounding box of apiaries + margin, limited zoom range). Show size estimate and progress.
- Areas not downloaded may show no basemap offline — pins and the apiary list must still work.
- Geocoding/place search only online; degrade gracefully offline.

---

## 9. Voice entry

### 9.1 Flow (client side)

```text
idle ──hold button──► listening (on-device recognizer, lang = locale) ──release──► transcript
  ▲                                                                                 │
  │                     online? ──no──► INSERT voice_notes (pending) → haptic saved → speak "saved for later" → idle
  │                        │yes
  │                        ▼
  │            POST /v1/voice/sessions { transcript, context, locale, client_time }
  │                        │
  │    ┌─────────────┬─────┴───────┬──────────────┬──────────────┐
  │  question      confirm     not_understood    saved        cancelled
  │  speak+listen  speak+listen  speak+listen    haptic saved  speak → idle
  │    │             │             │             highlight
  │    └──── POST /v1/voice/sessions/{thread_id}/reply { text } ◄┘   record → idle
  └──────────────────────────────────────────────────────────────────────────────┘
```

- **Push-to-talk only** (on-screen button or Bluetooth headset media button). No wake word.
- The session state machine lives in `src/voice/` (zustand store or reducer). Keep `thread_id` until `saved`/`cancelled`.
- Send **context**: if started from a colony/apiary screen, include their IDs (the server then doesn't need to ask "Care stup?").
- Show `draft` from each response in big text so the user can glance at it.
- **Nothing is saved without "da"/"yes".** The server always reads amounts back.
- The server saves the record; it arrives through PowerSync. Use `record.id` to highlight it immediately.

### 9.2 Voice API

Base `https://bee4you-backend.vercel.app`, `Authorization: Bearer <supabase token>`.

| Endpoint | Body | Use |
| --- | --- | --- |
| `POST /v1/voice/sessions` | `{ "transcript", "context": { "colony_id", "apiary_id" }, "locale": "ro-RO", "client_time" }` | Start an entry |
| `POST /v1/voice/sessions/{thread_id}/reply` | `{ "text": "da" }` | Answer a question / confirm. Re-sending the same reply after a dropped response is safe. |
| `GET /v1/voice/sessions/{thread_id}` | — | Repeat the pending question (app was closed mid-conversation) |
| `POST /v1/voice/notes/{voice_note_id}/process` | — | Start (or resume) the conversation for an offline voice note |
| `POST /v1/voice/transcribe` | multipart `audio` (≤ 4 MB; m4a/mp3/wav/webm/ogg/flac), `language=ro` | Server speech-to-text when the phone's recognizer can't be used **while online** |

Every voice response is a **turn**:

```jsonc
{ "thread_id": "uuid",
  "status": "question" | "confirm" | "not_understood" | "saved" | "cancelled",
  "speak": "Tratament pentru Stup 12: Acid oxalic, 5 mililitri, azi. Salvez?",
  "haptic": "needs_answer" | "saved" | "not_understood",
  "draft": { /* what the assistant understood so far */ },
  "record": { "table": "treatments", "id": "uuid" } | null }
```

| `status` | App does |
| --- | --- |
| `question`, `confirm` | Speak `speak`, play `haptic` (`needs_answer`), listen, send `/reply` |
| `not_understood` | Speak, play `not_understood`, listen again, send `/reply` |
| `saved` | Play `saved`, speak "Salvat." / "Saved.", highlight `record`, end |
| `cancelled` | Speak (nothing was saved), play `not_understood`, end |

Errors:

| HTTP | `error.code` | App does |
| --- | --- | --- |
| 401 | `unauthorized` | Refresh the session, retry once |
| 404 | `not_found` | Conversation is gone — start over |
| 503 | `assistant_unavailable` | **Keep the transcript as a pending `voice_note`** (same as offline) and say so |
| 422 | `voice_save_failed` | Say it couldn't be saved; open the typed form prefilled from the last `draft` |
| timeout / network | — | Retry the same request (idempotent); if offline now, fall back to a pending voice note |

### 9.3 Offline voice and language

- **Romanian and English.** Send the profile `locale` (`ro-RO` / `en-US`). The server asks and reads back in that language ("Cât ai folosit?", "25 de mililitri", "Salvat.") and accepts "da"/"nu"/"anulează" as well as "yes"/"no"/"cancel".
- Use the same locale for `expo-speech-recognition` and `expo-speech`. Phrases the **app** speaks itself (offline "saved for later", errors) live in `src/voice/phrases.ts` in both languages.
- **Offline speech-to-text is on the phone.** Request on-device recognition when offline. Whether Romanian works offline depends on the phone (Android: offline language pack; iOS: version). At startup and in Settings, check whether on-device recognition supports the chosen locale and show it ("Vocea funcționează offline: da/nu").
- If offline recognition isn't available, don't record (the backend needs a transcript; audio-only notes aren't supported) — tell the user and offer the typed form.
- Offline result → `INSERT voice_notes` (`transcript`, `locale`, context ids, `status = 'pending'`). It syncs up like any row.
- When back online → show "N voice notes to confirm" (Sync screen / banner) and process each **with the user present** via `/process`, which runs the same conversation. **Never auto-save.** The note's `status` and result fields are updated by the server and sync back.

### 9.4 Haptics (exactly three semantic patterns, in `src/voice/haptics.ts`)

| Meaning | Pattern | Used for |
| --- | --- | --- |
| `saved` | single short success | any local save (typed or voice), saved voice note |
| `needs_answer` | double tap | assistant asks a question / confirmation |
| `not_understood` | long / error | recognition failed, not understood, cancelled |

### 9.5 Speech settings

- Recognition & TTS locale from the user profile (`profiles.locale`), selectable in Settings.
- Request mic & speech permissions with a clear explanation; handle denial gracefully (typed entry still works).

---

## 10. API client (`src/lib/api.ts`)

- Base URL `EXPO_PUBLIC_API_URL` = `https://bee4you-backend.vercel.app` (also fine for development — no local backend or LAN IP needed). Live API docs: `/docs`.
- Always attach `Authorization: Bearer <supabase access token>`.
- Types generated from `/openapi.json` (e.g. `openapi-typescript`) — don't hand-write response types that can drift.
- Used **only** for: `POST /v1/sync/upload` (connector), the voice endpoints (§9.2), `GET /v1/me`. Everything else is read from local SQLite.
- Errors always look like `{ "error": { "code", "message", "details" } }`.
- Timeouts on every call (voice: ~20 s); voice calls show a "mă gândesc…" / "thinking…" state.

---

## 11. Coding conventions (TypeScript)

- `strict: true`; no `any` in domain code; prefer `type` aliases for data shapes, mirroring backend snake_case column names in DB row types; map to camelCase only in UI-facing view models if useful (be consistent per feature).
- Components: function components + hooks. One component per file. Name files `PascalCase.tsx` for components, `camelCase.ts` for hooks/utils (`useColony.ts`).
- Feature module shape: `features/<name>/{components/, hooks/, queries.ts, mutations.ts, schema.ts (zod), types.ts}`.
- Styling with NativeWind classes; shared primitives in `src/components/`.
- Env vars only via `src/lib/env.ts` (validated at startup).
- All user-facing text through `src/i18n` (`ro`, `en`) — no hard-coded strings in components.
- Dates: store UTC strings; format in the user's locale/timezone at display time.
- Lint/format: ESLint (expo config) + Prettier. Run `npx tsc --noEmit` before committing.
- Accessibility: `accessibilityLabel` on icon buttons; respect system font scaling.

---

## 12. Testing

| What | How |
| --- | --- |
| Feature logic (mutations, history merge, stock calc, zod schemas vs §4.0) | Jest + React Native Testing Library |
| Upload connector | Unit test with mocked fetch: applied / conflict / rejected stored / 5xx retry / 401 refresh / other 4xx doesn't jam |
| Voice state machine | Unit tests for each transition (question → reply → confirm → saved, cancelled, 503 → pending note, offline → pending note) |
| Against the live backend | `backend/scripts/smoke_live.py` proves the API works; for the app, sign in with a test user and use PowerSync's **Sync Test** page |
| Field checks (manual, on a real device) | Airplane mode: log harvest → kill app → reopen (still there) → reconnect → exactly one server row. Gloves: complete a treatment by voice, in Romanian. Offline: record a voice note, reconnect, confirm it. |

---

## 13. Roadmap — what the frontend delivers per phase

| Phase | Frontend deliverables | Backend status | Done when |
| --- | --- | --- | --- |
| **1 · Apiaries & colonies** | Expo dev build, Expo Router skeleton, NativeWind, i18n (ro/en), Supabase sign-in, PowerSync connection, map with pins, apiary list, colony profile, move colony, colony history | ✅ live | Move a colony between sites and find both placements in its history. |
| **2 · Field records** | Treatment / harvest / inventory / note forms, contextual quick entry, inventory stock view | ✅ live | Record a treatment from a colony screen without reselecting the colony. |
| **3 · Offline field testing** | Robust upload connector, sync badge & Sync screen, rejected ops, offline map regions, unsynced-changes warning on sign-out | ✅ upload/conflict logging live; conflict **review** endpoints not built yet | Harvest in airplane mode → restart → reconnect → one server entry. |
| **4 · Voice assistant** | Push-to-talk, on-device recognition, TTS read-back, haptics, voice session state machine, pending voice notes, Romanian | ✅ live (Groq, ro + en) | Say a treatment with gloves on, answer one follow-up, confirm, find the correct record. |
| **5 · Assistant extras** | Spoken history questions, treatment reminders (local notifications) | not built | Ask about a colony's last treatment and hear the right date and product. |
| **Later** | Photo capture for frame / varroa analysis | not built (no Storage buckets yet) | TBD |

**Do not build ahead of the phase** unless it's cheap and doesn't lock decisions.

---

## 14. Environment variables

```bash
EXPO_PUBLIC_SUPABASE_URL=https://atrvkrxfcdtkoeyczjct.supabase.co
EXPO_PUBLIC_SUPABASE_ANON_KEY=        # Supabase → Project Settings → API keys → publishable key
EXPO_PUBLIC_POWERSYNC_URL=            # PowerSync dashboard → instance URL (https://….powersync.journeyapps.com)
EXPO_PUBLIC_API_URL=https://bee4you-backend.vercel.app
EXPO_PUBLIC_MAP_STYLE_URL=            # MapTiler / Stadia style URL incl. restricted key
```

Everything `EXPO_PUBLIC_*` is visible in the app bundle — so **nothing secret** ever goes here.

---

## 15. Out of scope (for now)

- Expo Go support.
- A web version / web dashboard.
- Always-listening wake word.
- Writing records directly to Supabase tables from the app.
- Talking to the LLM or Groq directly from the app.
- Audio-only voice notes (a transcript is required).
- Photo/audio uploads to Supabase Storage (no buckets yet).
- Shared apiaries / team accounts.

---

## 16. Decision log

| Date | Decision | Why |
| --- | --- | --- |
| 2026-11-19 | App lives in `frontend/` (README proposed `apps/mobile`). | Clear frontend/backend split, each with its own architect doc. |
| 2026-11-19 | Local SQLite (PowerSync) is the UI's source of truth; writes never go directly to the network. | Offline-first field use. |
| 2026-11-19 | Rejected upload ops are completed (not retried forever) and shown on the Sync screen. | A bad record must not jam the upload queue. |
| 2026-11-19 | Proposed helpers: react-hook-form + zod, zustand, expo-secure-store, date-fns. | Not specified in README; confirm or replace. |
| 2026-11-25 | §4.0 data contract copied from the live backend; `attachments` dropped. | The backend is deployed; the app must send exactly what it validates. |
| 2026-11-25 | PowerSync Sync Streams with one auto-subscribed stream: the app only connects. | Backend uses `edition: 3`; all of a user's rows go to their phones. |
| 2026-11-25 | Development uses the deployed API (`bee4you-backend.vercel.app`). | No local backend needed; same behaviour as production. |
| 2026-11-25 | Voice works in Romanian and English; speech-to-text runs on the phone (offline when supported); the server only interprets. | User requirement; Groq needs internet. |
| 2026-11-25 | A failed or offline voice entry becomes a pending `voice_note` (transcript required), confirmed later. | Never lose what the user said; never auto-save. |
| 2026-11-25 | **No NativeWind:** React Native `StyleSheet` + tokens in `src/theme/tokens.ts`, shared primitives in `src/components/ui.tsx`. | NativeWind docs only confirm SDK 57 and its install conflicts with Expo 58's React version. Revisit when it supports SDK 58. |
| 2026-11-25 | Supabase session in `expo-secure-store`, split into chunks (`src/lib/secureStorage.ts`); not `expo-sqlite/localStorage`. | Encrypted; avoids shipping a second SQLite next to PowerSync's op-sqlite. |
| 2026-11-25 | Local-only table `upload_rejections` keeps ops the server rejected (Sync screen). | After the next sync a rejected change disappears from the synced tables. |
| 2026-11-25 | UI language stored on the device and in `profiles.locale`; default Romanian. | Primary user is Romanian; the profile drives the voice assistant's language. |
| 2026-11-25 | Phase 1 started without the map; apiary list first. Moves are dated "now" (no date picker yet). | Map needs a MapTiler key; the list is the offline-safe core. |
