# Frontend Architect — Bee4You

> **Purpose of this file.** This is the single source of truth for how the Bee4You mobile app is built.
> Before (and after) every frontend prompt, check the change against this document.
> If a change needs to break a rule here, **update this file first** (and add a line to the Decision Log at the bottom) — never let the code and this file drift apart.
> The backend counterpart is `backend/BackendArchitect.md`. Shared contracts (tables, units, API shapes) must match it.

---

## 0. Quick checklist for every frontend prompt

- [ ] **Works offline.** Any field action (create/edit a colony, treatment, harvest, inventory, note, move) writes to **local SQLite via PowerSync** and succeeds with no network.
- [ ] **Never call the API or supabase-js to write records.** Writes go to the local DB; the PowerSync connector uploads them. (supabase-js = Auth + Storage only; API client = upload connector + voice.)
- [ ] **New records get a client-generated UUID** and set `client_updated_at` on every edit.
- [ ] **Deletes are soft** (`deleted_at = now`); every query filters `deleted_at IS NULL`.
- [ ] **Reads come from local SQLite** (`useQuery` reactive queries), not from network fetches.
- [ ] **New table/column?** It must exist in the backend migration + sync rules first; then update `src/db/schema.ts`. Names identical to the backend.
- [ ] **Glove-friendly UI:** touch targets ≥ 56 dp, primary action reachable one-handed, high contrast for sunlight, no tiny icons-only controls for important actions.
- [ ] **"Saved" ≠ "synced".** Show local save (haptic + toast) separately from sync status.
- [ ] **Contextual quick entry:** if the user is on a colony/apiary screen, that colony/apiary is pre-selected.
- [ ] **Voice entry produces the same record** a typed entry would — no voice-only data shapes.
- [ ] **No secrets in the app.** Only `EXPO_PUBLIC_*` values (URLs, anon key, map key restricted to the app). Never the Anthropic key.
- [ ] **TypeScript strict, no `any`** in domain code.
- [ ] Change belongs to the **current roadmap phase** (section 13).

---

## 1. What the frontend is

Bee4You is a **mobile field notebook** for beekeepers with permanent or migratory apiaries. The user picks a colony, logs work at the hive, and puts the phone away — **even without signal**. Hands are gloved and sticky, so entries can also be made **by voice** (push-to-talk → assistant fills the form → reads it back → vibrates on save).

The app is **offline-first**: the local SQLite database (PowerSync) is the source of truth for the UI. The network is only needed for sign-in, the first download, syncing, and the voice assistant.

```text
Mobile app (Android / iOS) — React Native + Expo (development build)
  ├── SQLite via PowerSync     → all records, offline upload queue
  ├── MapLibre + OSM tiles     → apiary map, offline map regions
  ├── Speech / TTS / haptics   → voice entry
  ├── supabase-js              → sign-in, session refresh, Storage uploads
  └── API client (FastAPI)     → PowerSync upload handler, voice sessions
```

---

## 2. Technology stack (fixed — do not swap without a Decision Log entry)

| Technology | Role | Rules |
| --- | --- | --- |
| React Native + TypeScript + **Expo (development build)** | Android & iOS from one codebase | Expo Go is **not** supported (native modules for maps & speech). Use `npx expo install` for native deps. |
| **Expo Router** | File-based navigation | Screens in `src/app/`. Keep screen files thin. |
| **NativeWind** | Styling (Tailwind classes) | Use design tokens from `tailwind.config.js`; no ad-hoc hex colors in components. |
| **@maplibre/maplibre-react-native** | Map, apiary markers, offline regions | Vector tiles from MapTiler/Stadia. **Never** `tile.openstreetmap.org`. |
| **MapTiler or Stadia Maps** | Tile hosting + geocoding | Key restricted to the app bundle id. |
| **@powersync/react-native** (+ `@powersync/react`) | Local SQLite, reactive queries, upload queue | The only data layer for records. |
| **@supabase/supabase-js** | Auth, session refresh, Storage | **No table reads/writes** through it. |
| **expo-speech-recognition** | Speech → text (on-device where supported) | Push-to-talk only. |
| **expo-speech** | Text → speech (offline) | Reads questions & confirmations. |
| **expo-haptics** | Vibration patterns | Exactly three semantic patterns (section 9.3). |

Proposed helpers (not in the README; adopt or replace, then record in the Decision Log):

| Helper | Role |
| --- | --- |
| `react-hook-form` + `zod` | Forms + validation; zod schemas shared by typed and voice-draft forms |
| `zustand` | Small ephemeral UI state (voice session state, map camera). Not for records. |
| `expo-secure-store` | Persist Supabase session securely |
| `date-fns` | Date formatting/parsing |
| `uuid` (v4) or `expo-crypto.randomUUID()` | Client-generated IDs |

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
    │   ├── _layout.tsx          # providers: PowerSync, Auth, theme
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
    │       ├── sync.tsx                         # sync status, rejected ops, conflicts
    │       └── settings/index.tsx               # language, units, offline maps, sign out
    ├── features/                # domain modules: components + hooks + queries + mutations
    │   ├── apiaries/
    │   ├── colonies/            # incl. placements & moves
    │   ├── treatments/
    │   ├── harvests/
    │   ├── inventory/
    │   ├── notes/
    │   └── sync/                # status indicator, conflict review
    ├── voice/                   # push-to-talk, recognizer, TTS read-back, haptics, voice API client, session state machine
    ├── db/
    │   ├── schema.ts            # PowerSync schema — mirrors backend tables
    │   ├── powersync.ts         # database instance
    │   ├── connector.ts         # fetchCredentials (Supabase token) + uploadData (→ FastAPI)
    │   └── queries/             # shared SQL helpers
    ├── lib/
    │   ├── supabase.ts          # supabase client (auth + storage)
    │   ├── api.ts               # typed FastAPI client (types generated from OpenAPI)
    │   ├── map.ts               # style URL, offline region helpers
    │   ├── ids.ts               # newId(), nowIso()
    │   ├── units.ts             # unit enum + formatting
    │   └── env.ts               # validated EXPO_PUBLIC_* config
    ├── components/              # generic UI: BigButton, Field, NumberPad, SyncBadge, EmptyState
    └── theme/                   # tokens, typography
```

**Layering rule:** `app/` (screens) → `features/*` (hooks, components) → `db/` & `lib/`. Screens never write SQL directly; they call feature hooks (`useColony`, `useCreateTreatment`). `voice/` reuses feature mutations — it does not have its own save path.

---

## 4. Data layer (PowerSync) — the core of the app

### 4.1 Schema mirrors the backend

`src/db/schema.ts` declares the same tables and column names as the backend (see `backend/BackendArchitect.md` §4.2):

`profiles`, `apiaries`, `colonies`, `colony_placements`, `inventory_items`, `inventory_adjustments`, `treatments`, `harvests`, `colony_notes`, `attachments`, `voice_notes` (+ read-only conflict summary if exposed).

Differences that are expected:

- `apiaries` has `lat` / `lng` (REAL) instead of a PostGIS point.
- SQLite types: UUIDs and timestamps are `TEXT` (ISO-8601 UTC), numbers `REAL`/`INTEGER`, booleans `INTEGER` 0/1. Convert in the feature layer, not in components.
- `owner_id` exists locally but is **never trusted** by the server — set it to the current user id for local queries anyway.

**Order of change:** backend migration → sync rules → `schema.ts` → features. Never add a local-only column that the backend doesn't know about (except PowerSync `localOnly` tables, which must be documented here).

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
  if (itemId) {
    // stock side effect in the SAME transaction (backend §6.4)
    await tx.execute(`INSERT INTO inventory_adjustments (...) VALUES (...)`, [newId(), ..., -amount, 'used', id]);
  }
});
haptics.saved();                        // local save confirmed
```

Rules:

- **Related writes in one `writeTransaction`** (move = close old placement + open new one; treatment + stock adjustment).
- **Update** = set changed fields + `client_updated_at = now`.
- **Delete** = `UPDATE ... SET deleted_at = now, client_updated_at = now`.
- Validate with the feature's zod schema **before** writing.
- Amounts: positive numbers; units from the shared enum only (`ml`, `l`, `g`, `kg`, `pcs`, `strips`, `frames`).

### 4.3 Reading records

- Use reactive `useQuery` from `@powersync/react` inside feature hooks; screens re-render automatically when sync brings new data.
- Always `WHERE deleted_at IS NULL`.
- **Colony history** = union of placements + treatments + harvests + notes for that colony, sorted by event date, each showing the **apiary where it happened** (from the record's own `apiary_id`, not the colony's current apiary).
- **Current apiary of a colony** = placement with `ended_at IS NULL`.
- **Inventory stock** = `SUM(delta)` of adjustments per item (and per apiary if needed).

### 4.4 Upload connector (`src/db/connector.ts`)

- `fetchCredentials()` → PowerSync endpoint (`EXPO_PUBLIC_POWERSYNC_URL`) + current Supabase access token (refresh if needed).
- `uploadData()` → reads the CRUD batch, maps to `{ ops: [{ op, table, id, data }] }`, `POST /v1/sync/upload` with `Authorization: Bearer <supabase token>`.
  - Response per op: `applied` / `conflict` / `rejected`.
  - On HTTP 200 → `transaction.complete()` (even with rejected ops — store them for the Sync screen so the user sees what failed).
  - On network error / 5xx / 401 → throw so PowerSync retries (after refreshing the token on 401).
- Never drop the queue silently; never block the queue forever on one bad op.

---

## 5. Auth

- Supabase Auth: email, Google, Apple. Session persisted with `expo-secure-store`; `autoRefreshToken: true`.
- On first sign-in **online**: connect PowerSync → initial download of apiaries/colonies/records. Show a clear "Downloading your apiaries…" state.
- Subsequent launches work **offline** with the cached session and local DB.
- Expired session while offline: keep the app usable locally; uploads pause; prompt for sign-in when back online (show it in the sync badge, not as a blocking modal in the field).
- Sign-out: warn if there are **unsynced changes** (they would be lost), then disconnect and clear the local DB.

---

## 6. Navigation & screens

| Screen | Purpose | Key actions |
| --- | --- | --- |
| Map | MapLibre map with apiary pins | Tap pin → apiary; add apiary at location; current location |
| Apiaries list | Searchable list of saved apiaries — **always works offline**, even without map tiles | Open apiary, add apiary |
| Apiary | Colonies currently placed here, recent harvests | Open colony, **log harvest**, **adjust inventory**, add colony |
| Colony | Header (label, mode, status, current apiary) + history timeline | **Quick entry**: treatment / note / move; voice button |
| Move colony | Choose destination apiary + move date | Writes placement close/open |
| Entry forms | Treatment, harvest, inventory, note — prefilled from context | Save (big button) |
| Voice | Push-to-talk session overlay | Hold to talk, see draft, hear questions/confirmation |
| Sync | Sync status, pending count, rejected ops, conflicts | Retry, review conflict |
| Settings | Language (speech + UI), default units, offline map regions, account | Download region, sign out |

**Contextual quick entry is a core feature:** `entry/treatment?colonyId=X&apiaryId=Y` pre-selects both; the user should never reselect the colony they're standing at. (Phase 2 completion check.)

---

## 7. Field UX rules (gloves, sun, bees)

- Touch targets **≥ 56 dp**; primary "Save" button full-width at the bottom, reachable with a thumb.
- Large fonts for key values (amounts, hive labels); high-contrast theme readable in direct sunlight. Support dark mode, but test light mode outdoors.
- Prefer **steppers, chips, and big number pads** over free-text keyboards. Recent products / last-used amount as one-tap chips.
- Minimal required fields; sensible defaults (date = now, unit = last used for that product).
- Every save gives **immediate feedback**: haptic + short toast, then navigate back.
- No destructive action without confirmation; prefer undo toasts for deletes.
- Never show a spinner that blocks a field action waiting for the network.
- Sync status always visible but unobtrusive (badge: ✓ synced / ↑ N pending / ⚠ attention).

---

## 8. Maps

- Style URL from MapTiler or Stadia (`lib/map.ts`), key from `EXPO_PUBLIC_MAP_STYLE_URL` / key env var, restricted to the app.
- **Never use `tile.openstreetmap.org`** (usage policy forbids app traffic). Show OSM attribution as required by the provider.
- Offline regions: Settings → "Download area around my apiaries" (bounding box of apiaries + margin, limited zoom range). Show size estimate and progress.
- Areas not downloaded may show no basemap offline — pins and the apiary list must still work.
- Geocoding/place search only online; degrade gracefully offline.

---

## 9. Voice entry

### 9.1 Flow (client side)

```text
idle ──hold button──► listening ──release──► transcribing
  ▲                                               │
  │                       online? ──no──► save voice_notes row (pending) → haptic "saved" → idle
  │                          │yes
  │                          ▼
  │                   POST /v1/voice/sessions  (transcript + context colony/apiary + locale)
  │                          │
  │             ┌────────────┼──────────────┬────────────────┐
  │         question       confirm         saved       not_understood
  │      speak + haptic  speak summary   haptic saved   speak + haptic
  │      "needs_answer"  + "needs_answer"   → idle        → listening
  │      → listening     → listening
  │      → POST .../reply → (loop)
  └──────────────────────────────────────────────────────────┘
```

- **Push-to-talk only** (on-screen button or Bluetooth headset media button). No wake word.
- The session state machine lives in `src/voice/` (zustand store or reducer). Keep `thread_id` until `saved`/`cancelled`.
- Send **context**: if started from a colony/apiary screen, include their IDs.
- Show the draft visually too (big text) so the user can glance at it.
- **Nothing is saved without "yes".** Amounts are always read back (speech confuses "15"/"50").
- The server saves the record and it arrives via PowerSync; use the returned `record` id to highlight it immediately.

### 9.2 Offline voice

- Speech recognition and TTS can work offline (language-dependent). The assistant cannot.
- Offline → store a `voice_notes` row (`transcript`, optional audio via Storage later, context IDs, `status = pending`).
- When back online → list pending voice notes and process each with the user present (`POST /v1/voice/notes/{id}/process`), asking for confirmation then. **Never auto-save.**

### 9.3 Haptics (exactly three semantic patterns, in `src/voice/haptics.ts`)

| Meaning | Pattern | Used for |
| --- | --- | --- |
| `saved` | single short success | any local save (typed or voice) |
| `needs_answer` | double tap | assistant asks a question / confirmation |
| `not_understood` | long / error | recognition or parsing failed |

### 9.4 Speech settings

- Recognition & TTS locale from the user profile (`profiles.locale`), selectable in Settings.
- Request mic & speech permissions with a clear explanation; handle denial gracefully (typed entry still works).

---

## 10. API client (`src/lib/api.ts`)

- Base URL `EXPO_PUBLIC_API_URL`. On a physical phone, `localhost` is the phone — use the computer's LAN IP in development.
- Always attach `Authorization: Bearer <supabase access token>`.
- Types generated from the backend OpenAPI (`/openapi.json`, e.g. `openapi-typescript`) — don't hand-write response types that can drift.
- Used **only** for: `POST /v1/sync/upload` (connector), voice endpoints, conflict review, optional complex reads (`/v1/colonies/{id}/history`), `/v1/me`.
- Timeouts on every call; voice calls show a "thinking…" state and handle timeouts with `not_understood`-style feedback.

---

## 11. Coding conventions (TypeScript)

- `strict: true`; no `any` in domain code; prefer `type` aliases for data shapes, mirroring backend snake_case column names in DB row types; map to camelCase only in UI-facing view models if useful (be consistent per feature).
- Components: function components + hooks. One component per file. Name files `PascalCase.tsx` for components, `camelCase.ts` for hooks/utils (`useColony.ts`).
- Feature module shape: `features/<name>/{components/, hooks/, queries.ts, mutations.ts, schema.ts (zod), types.ts}`.
- Styling with NativeWind classes; shared primitives in `src/components/`.
- Env vars only via `src/lib/env.ts` (validated at startup).
- Dates: store ISO UTC strings; format in the user's locale/timezone at display time.
- Lint/format: ESLint (expo config) + Prettier. Run `npx tsc --noEmit` before committing.
- Accessibility: `accessibilityLabel` on icon buttons; respect system font scaling.

---

## 12. Testing

| What | How |
| --- | --- |
| Feature logic (mutations, history merge, stock calc, zod schemas) | Jest + React Native Testing Library |
| Upload connector | Unit test with mocked fetch: applied / rejected / 5xx retry / 401 refresh |
| Voice state machine | Unit tests for each transition (question → reply → confirm → saved, offline → pending note) |
| Field checks (manual, on a real device) | Airplane mode: log harvest → kill app → reopen (still there) → reconnect → exactly one server row. Gloves: complete a treatment by voice. |

---

## 13. Roadmap — what the frontend delivers per phase

| Phase | Frontend deliverables | Done when |
| --- | --- | --- |
| **1 · Apiaries & colonies** | Expo dev build, Expo Router skeleton, NativeWind, Supabase sign-in, PowerSync connection, map with pins, apiary list, colony profile, move colony, colony history | Move a colony between sites and find both placements in its history. |
| **2 · Field records** | Treatment / harvest / inventory / note forms, contextual quick entry, inventory stock view | Record a treatment from a colony screen without reselecting the colony. |
| **3 · Offline field testing** | Robust upload connector, sync badge & Sync screen, rejected ops + conflict review, offline map regions, unsynced-changes warning on sign-out | Harvest in airplane mode → restart → reconnect → one server entry. |
| **4 · Voice assistant** | Push-to-talk, speech recognition, TTS read-back, haptics, voice session state machine, pending voice notes | Say a treatment with gloves on, answer one follow-up, confirm, find the correct record. |
| **5 · Assistant extras** | Spoken history questions, treatment reminders (local notifications) | Ask about a colony's last treatment and hear the right date and product. |
| **Later** | Photo capture for frame / varroa analysis | TBD |

**Do not build ahead of the phase** unless it's cheap and doesn't lock decisions.

---

## 14. Environment variables

```bash
EXPO_PUBLIC_SUPABASE_URL=
EXPO_PUBLIC_SUPABASE_ANON_KEY=
EXPO_PUBLIC_POWERSYNC_URL=
EXPO_PUBLIC_API_URL=          # LAN IP of your computer in dev, e.g. http://192.168.x.x:8000
EXPO_PUBLIC_MAP_STYLE_URL=    # MapTiler / Stadia style URL incl. restricted key
```

Everything `EXPO_PUBLIC_*` is visible in the app bundle — so **nothing secret** ever goes here.

---

## 15. Out of scope (for now)

- Expo Go support.
- A web version / web dashboard.
- Always-listening wake word.
- Writing records directly to Supabase tables from the app.
- Talking to the LLM directly from the app.
- Shared apiaries / team accounts.

---

## 16. Decision log

| Date | Decision | Why |
| --- | --- | --- |
| 2026-11-19 | App lives in `frontend/` (README proposed `apps/mobile`). | Clear frontend/backend split, each with its own architect doc. |
| 2026-11-19 | Local SQLite (PowerSync) is the UI's source of truth; writes never go directly to the network. | Offline-first field use. |
| 2026-11-19 | Rejected upload ops are completed (not retried forever) and shown on the Sync screen. | A bad record must not jam the upload queue. |
| 2026-11-19 | Proposed helpers: react-hook-form + zod, zustand, expo-secure-store, date-fns. | Not specified in README; confirm or replace. |
