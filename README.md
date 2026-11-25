# Bee4You

Bee4You is a planned mobile field notebook for beekeepers who manage colonies at permanent apiaries or move them between sites during the season. The aim is to let a beekeeper select a colony, log work at the hive, and put the phone away even when there is no signal. Because hands are gloved and sticky at the hive, entries can also be made by voice: the app listens, reads the entry back through the speaker, and vibrates when it is saved.

**Project status:** Planning. The features, architecture, folder layout, and setup steps below describe the intended implementation.

## A visit to the apiary

1. **Find the site.** Select an apiary pin on the OpenStreetMap-based map or open a previously saved site from the apiary list.
2. **Choose a colony.** Open its history. A stationary colony can stay at one site throughout the season. For a migratory colony, record the move date, origin, and destination so earlier visits remain linked to the site where they took place.
3. **Make a quick entry.** From the colony screen, start a treatment with the colony and apiary already selected. Record the product, date, and amount used. From the apiary screen, log a harvest with its quantity and unit, or adjust inventory when supplies arrive or equipment moves.
4. **Or say it.** Hold the talk button and speak, for example: *"Hive 12, oxalic acid, 5 ml, queen seen, calm."* The assistant fills in the same form, asks about anything missing, reads the entry back, and saves it when you say "yes".
5. **Save in the field.** A short vibration confirms that the phone has stored the entry. A separate sync status shows whether the server has received it.

## Architecture and technology stack

```text
Mobile app (Android / iOS)
React Native + Expo
  ├── SQLite via PowerSync (field records, offline queue)
  ├── MapLibre + OpenStreetMap tiles (map, offline regions)
  └── Speech recognition, text-to-speech, haptics (voice entry)
        │                                  │
        │ sign-in, sync                    │ voice entries, uploads, complex logic
        ▼                                  ▼
   Supabase                             FastAPI (Python)
   Auth · Postgres + PostGIS ◄────────── LangGraph assistant (LangChain + Groq)
   Storage · Row Level Security          Verifies Supabase JWTs
        ▲
        │ PowerSync service streams changes to devices
```

The app signs in with Supabase Auth and sends the same access token to FastAPI, so there is one login and one database.

### Mobile frontend

| Technology | Role |
| --- | --- |
| React Native, TypeScript, Expo (development build) | Build the Android and iOS field app from a shared codebase. Native modules for maps and speech require a development build rather than Expo Go. |
| Expo Router | Navigate between the map, apiary, colony history, entry, and voice screens. |
| NativeWind | Style forms, lists, map controls, and sync indicators consistently. |
| @maplibre/maplibre-react-native | Display apiary markers on OpenStreetMap-based vector tiles and download map regions for offline use. |
| MapTiler or Stadia Maps | Host map tiles and place search (geocoding). The public `tile.openstreetmap.org` server is not used, because its usage policy does not allow app traffic. |
| PowerSync React Native SDK | Keep a local SQLite copy of the beekeeper’s records, queue changes made offline, and sync them with Supabase. |
| @supabase/supabase-js | Sign in, refresh sessions, and upload photos or voice recordings to Supabase Storage. |
| expo-speech-recognition | Turn spoken entries into text using the phone’s built-in recognizer, on-device where the language supports it. |
| expo-speech | Read questions and confirmations aloud through the phone speaker, offline. |
| expo-haptics | Give distinct vibration patterns for “saved”, “needs an answer”, and “not understood”. |

### Backend

| Technology | Role |
| --- | --- |
| Supabase Auth | Handle sign-in (email, Google, Apple) and issue the JWTs used by the app, PowerSync, and FastAPI. |
| Supabase Postgres, PostGIS | Hold the central records shared across a beekeeper’s devices, including apiary locations. |
| Row Level Security | Ensure each user can only read and change their own apiaries, colonies, and records. |
| Supabase Storage | Store hive photos and voice recordings. |
| Supabase CLI migrations | Own the database schema. All table changes go through `backend/supabase/migrations`. |
| PowerSync service | Stream server changes to each device according to sync rules. |
| Python, FastAPI, Pydantic | Expose the API for uploads from the device queue, voice entries, and logic too complex for direct database access. Request and response models generate the OpenAPI docs. |
| SQLAlchemy (async) | Query and write Postgres from FastAPI. It does not create or alter tables. |

### AI assistant

| Technology | Role |
| --- | --- |
| LangGraph | Run the voice-entry conversation as a graph with steps for extraction, lookup, follow-up questions, and confirmation. |
| LangChain, langchain-groq | Call a Groq-hosted model (`openai/gpt-oss-20b`, free tier) with strict JSON-schema output, so each spoken entry (English or Romanian) becomes a validated treatment, harvest, inventory, or note record. |
| Groq Whisper | Server-side speech-to-text (`whisper-large-v3-turbo`) for recordings the phone can't transcribe, such as offline voice notes. |
| `voice_sessions` table | Save each LangGraph conversation in Postgres, in the same transaction as the saved record, so a follow-up question and its answer can arrive in separate requests. |
| LangSmith (optional) | Trace graph runs to debug misheard or misparsed entries. |

The Groq API key and all model calls stay on the FastAPI server. The app never talks to the model directly.

## Voice entry

The assistant offers a faster way to fill the existing forms. Every voice entry ends up as the same record a typed entry would create.

```text
transcript ──► extract ──► resolve ──► missing info? ──yes──► ask (interrupt) ──┐
                 ▲                          │no                                  │
                 └──────────────────────────┼────────── user's answer ◄──────────┘
                                            ▼
                                   confirm (interrupt) ──"yes"──► save record
                                            │"no" / correction
                                            └──► back to extract
```

1. **Extract.** The LLM turns the transcript into a typed draft (Pydantic model) such as a treatment with colony, product, amount, and unit.
2. **Resolve.** Plain code, not the LLM, matches “hive 12” to the user’s colonies and the product to their inventory. Unknown or ambiguous values become questions.
3. **Ask.** The graph pauses and returns a question. The app speaks it, listens for the answer, and resumes the same conversation.
4. **Confirm.** The graph returns a spoken summary. Nothing is saved until the beekeeper says yes. Amounts in particular are always read back, because speech recognition can confuse values such as “15” and “50”.
5. **Save.** The confirmed record is written through the same path as a typed entry, and the phone vibrates.

**Voice without signal.** Speech recognition and read-back can work offline, but the LangGraph step needs the server. When offline, the app stores the transcript (and optionally the audio) as a pending voice note in SQLite and processes it after reconnecting, asking for confirmation then.

**Listening mode.** Voice entry uses push-to-talk (an on-screen button or a Bluetooth headset button). An always-listening wake word is out of scope because of battery use and complexity.

## Offline saves and sync

On the first connected sign-in, PowerSync downloads the beekeeper’s apiaries and colonies into SQLite on the device. Later visits read and write that local copy. The proposed sync flow is:

1. Save the field entry locally. PowerSync records the change in its upload queue in the same transaction. Each record gets a client-generated UUID before upload.
2. When the device is online, the PowerSync upload handler sends queued changes to FastAPI. The API upserts by UUID, so a retried upload after a dropped connection cannot count the same harvest twice.
3. PowerSync streams accepted changes and newer server records back to every device. If two devices edit the same record, the API keeps the latest edit and flags the conflict for review.

**Field limits.** A new device needs a connection for sign-in and its first download. Unsynced entries exist only on the device and can be lost if app data is cleared. An expired session may require sign-in before uploads resume.

**Map limits.** MapLibre can download map regions for offline use, so a beekeeper can save the area around their apiaries before leaving signal. Areas that were not downloaded may show no basemap. The searchable list of saved apiaries, with their colonies and quick-entry forms, always works offline.

## Feature roadmap

| Phase | Planned milestone | Completion check |
| --- | --- | --- |
| 1 · Apiaries and colonies | Supabase sign-in, map and list views, colony profiles, stationary placements, and dated moves | Move a colony between sites and find both placements in its history. |
| 2 · Field records | Treatment logs, harvest quantities, inventory adjustments, and contextual quick entry | Record a treatment from a colony screen without reselecting the colony. |
| 3 · Offline field testing | PowerSync local saves, queued uploads, retry handling, conflict review, and offline map regions | Log a harvest in airplane mode, restart the app, reconnect, and verify one server entry. |
| 4 · Voice assistant | Push-to-talk, LangGraph extraction and follow-up questions, spoken confirmation, haptics, and pending voice notes | Say a treatment with gloves on, answer one follow-up question, confirm, and find the correct record. |
| 5 · Assistant extras | Spoken history questions (“what did I do to hive 12 last month?”) and treatment reminders | Ask about a colony’s last treatment and hear the right date and product. |
| Later | Photo analysis of frames and varroa counts | To be defined. |

The Supabase dashboard covers record review on a larger screen during development. A separate web dashboard is not planned for now.

## Project structure

```text
bee4you/
├── frontend/                     # Mobile app (React Native + Expo)
│   ├── FrontendArchitect.md      # Rules and contracts for all frontend work
│   └── src/
│       ├── app/                  # Expo Router screens and layouts
│       ├── features/             # Apiaries, colonies, treatments, harvests, inventory
│       ├── voice/                # Push-to-talk, speech recognition, read-back, haptics
│       ├── db/                   # PowerSync schema and local queries
│       └── lib/                  # Supabase client, API client, map config
├── backend/
│   ├── BackendArchitect.md       # Rules and contracts for all backend work
│   ├── app/
│   │   ├── api/                  # FastAPI routers (uploads, voice, records)
│   │   ├── auth/                 # Supabase JWT verification
│   │   ├── models/               # SQLAlchemy and Pydantic models
│   │   ├── services/             # Domain logic shared by typed and voice entries
│   │   └── assistant/            # LangGraph graph, nodes, prompts, tools
│   ├── tests/
│   ├── pyproject.toml
│   ├── supabase/
│   │   ├── migrations/           # Schema, RLS policies, PostGIS
│   │   └── seed.sql
│   └── powersync/
│       ├── sync-config.yaml      # PowerSync Sync Streams: which rows each user's devices receive
│       └── setup-role.sql        # One-time SQL for the PowerSync database role
└── README.md
```

Before working on either side, read its architect file: [frontend/FrontendArchitect.md](frontend/FrontendArchitect.md) or [backend/BackendArchitect.md](backend/BackendArchitect.md). Each one starts with a checklist for reviewing every change.

## Development setup plan

These steps are for scaffolding the project. Choose compatible versions and commit the lockfiles when the first projects are created.

1. **Prepare the tools.** Install Node.js LTS, Python 3.12+ with `uv` (or another environment manager), the Supabase CLI (Docker is optional, only for running Supabase locally; a hosted project works without it). Have an Android or iOS device for field testing. Local native builds require Android Studio for Android or macOS with Xcode for iOS.
2. **Create the Supabase project.** From `backend/`, run `supabase init` and `supabase start` for local development, and create a hosted project for the phone to reach. Enable PostGIS, write the first migration with the core tables and RLS policies, and turn on the sign-in providers you need. Free-tier hosted projects pause after about a week without activity.
3. **Set up PowerSync.** Create a PowerSync instance connected to the Supabase database, configure Supabase Auth as its JWT source, and write the first sync rules so each user receives only their own apiaries and colonies.
4. **Create the backend.** In `backend/`, scaffold a FastAPI project with `fastapi`, `uvicorn`, `pydantic`, `sqlalchemy[asyncio]`, `asyncpg`, `pyjwt`, `langchain-groq`, `langgraph`, and `python-multipart`. Configure `DATABASE_URL`, `SUPABASE_URL`, `SUPABASE_JWT_SECRET` (or the project’s JWKS URL), and `GROQ_API_KEY`. Keep these on the server only.
5. **Create the mobile project.** In `frontend/`, scaffold a TypeScript Expo app with Expo Router, then install the native dependencies: `npx expo install @maplibre/maplibre-react-native expo-speech-recognition expo-speech expo-haptics @powersync/react-native @supabase/supabase-js`. Configure NativeWind, build a development client, and set `EXPO_PUBLIC_SUPABASE_URL`, `EXPO_PUBLIC_SUPABASE_ANON_KEY`, `EXPO_PUBLIC_POWERSYNC_URL`, and `EXPO_PUBLIC_API_URL`. On a physical phone, `localhost` refers to the phone itself, so use your computer’s network address.
6. **Configure maps.** Create a MapTiler or Stadia Maps account, restrict the key to the app, and set the style URL in the mobile config.
7. **Verify the first field workflow.** Sign in, download one apiary, and disable connectivity. Save a treatment, close and reopen the app, then reconnect. Check that the treatment stays visible locally and appears exactly once in Supabase.
8. **Verify the first voice entry.** With a connection, say a treatment without the amount, answer the follow-up question, confirm, and check the saved record.
