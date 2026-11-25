# Deploying the Bee4You backend

Two pieces: **PowerSync** (sends each user's rows down to their phone) and **Vercel** (runs the FastAPI API: uploads from the phone, voice assistant). Supabase is already set up: migrations pushed, project `atrvkrxfcdtkoeyczjct`, region eu-west-1.

Secrets never go in git or in chat: the database passwords and `GROQ_API_KEY` go only into the PowerSync / Vercel dashboards and your local `backend/.env`.

---

## Part A — PowerSync

### A1. Database access for PowerSync

**Easiest: the "Set Up with Supabase" button** in the PowerSync dashboard. It creates its own database user (`powersync_<random>`) and connects automatically, so you can skip A3.

It also adds **every** table to the `powersync` publication and lets its user read all of them, including our server-only `voice_sessions` and `sync_conflicts`. Our migration `20261125000005_keep_server_tables_out_of_powersync.sql` undoes that for those two tables. Run `npx supabase db push --remote` after the button finishes. If you ever press the button again, re-run that file's SQL in the SQL Editor.

**Manual alternative:** run [`powersync/setup-role.sql`](powersync/setup-role.sql) in the Supabase SQL Editor (replace `CHANGE_ME` with a long random password), then connect with it in A3.

### A2. Create the PowerSync instance

1. Sign up / log in at https://dashboard.powersync.com.
2. Create a project, then **Add Instance**. Pick an EU region if offered (your Supabase project is in Ireland).

### A3. Connect it to Supabase (manual route only)

1. Supabase Dashboard → **Connect** (top bar) → **Direct connection** → copy the URI. Host: `db.atrvkrxfcdtkoeyczjct.supabase.co`, port `5432`.
   Use the **direct** connection, not the pooler: PowerSync needs Postgres replication, which the pooler doesn't support.
2. PowerSync Dashboard → your instance → **Database Connection** → **Postgres** tab:
   - **URI**: paste it.
   - **Username**: `powersync_role`
   - **Password**: the password from A1.
   - **SSL Mode**: keep `verify-full`.
3. **Test Connection** → **Save Connection**.

If the test fails, copy the exact error message. A network/IPv6 error and a permission error have different fixes.

### A4. Let PowerSync accept the app's Supabase login

PowerSync Dashboard → **Client Auth**:

- Turn on **Use Supabase Auth**.
- Leave **Supabase JWT Secret** **empty** (your project uses the new signing keys; PowerSync reads them from JWKS).
- **Save and Deploy**.

It should show JWKS URI `https://atrvkrxfcdtkoeyczjct.supabase.co/auth/v1/.well-known/jwks.json` and audience `authenticated`.

### A5. Deploy the Sync Streams

1. PowerSync Dashboard → **Sync Streams**.
2. Replace the editor contents with [`powersync/sync-config.yaml`](powersync/sync-config.yaml).
3. **Validate**, then **Deploy**.

If validation complains about `st_x` / `st_y` on `apiaries.location`, copy the message. The fallback is to send the point as text and parse it on the phone.

### A6. Note the instance URL

Copy the instance URL (looks like `https://<id>.powersync.journeyapps.com`). The app needs it as `EXPO_PUBLIC_POWERSYNC_URL`.

**Troubleshooting:** "All replication slots are in use" → in the Supabase SQL Editor run
`select slot_name, pg_drop_replication_slot(slot_name) from pg_replication_slots where active = false;`

---

## Part B — Vercel

The repo already has the config: `vercel.json` (region `dub1` = Dublin, next to Supabase; 60 s max per request), `.vercelignore`, and `[tool.vercel] entrypoint = "app.main:app"` in `pyproject.toml`.

### B1. Push the code

The deploy files must be on GitHub (`AlexMotoasca/Bee4You`, branch `Backend`).

### B2. Import the project

1. https://vercel.com/new → **Import** the `Bee4You` GitHub repo.
2. **Root Directory**: `backend` (click Edit next to it).
3. Framework preset: **FastAPI** (should be detected automatically).
4. Don't deploy yet; first open **Environment Variables** (next step).

### B3. Environment variables

Add these for **Production** and **Preview**:

| Name | Value |
| --- | --- |
| `DATABASE_URL` | the same **pooler** URL as in your `backend/.env` (port **6543**) |
| `DB_SERVERLESS` | `true` |
| `SUPABASE_URL` | `https://atrvkrxfcdtkoeyczjct.supabase.co` |
| `GROQ_API_KEY` | your Groq key |
| `ENVIRONMENT` | `production` |

Leave `SUPABASE_JWKS_URL` and `SUPABASE_JWT_SECRET` unset.

### B4. Which branch deploys

Vercel's **production** branch is `main`, but the backend currently lives on `Backend`. Either:

- **Recommended:** merge `Backend` into `main` (pull request), and production deploys from `main`; or
- temporarily set **Settings → Environments → Production → Branch Tracking** to `Backend`.

Pushes to other branches create **preview** deployments.

### B5. Deployment Protection (important for the phone)

Vercel puts **preview** deployments behind a Vercel login by default. The phone would get a login page instead of JSON. For a preview URL the app calls, turn it off under **Settings → Deployment Protection → Vercel Authentication**, or use the production URL (not protected by default).

### B6. Check it works

Replace `<url>` with your deployment URL:

```bash
curl https://<url>/health
```

Expected: `{"status":"ok"}`

```bash
curl https://<url>/v1/me
```

Expected: `401` with `{"error":{"code":"unauthorized",...}}`. Auth is wired, and there's no token.

The interactive API docs are at `https://<url>/docs`. The app needs this URL as `EXPO_PUBLIC_API_URL`.

---

## What the frontend needs afterwards

```bash
EXPO_PUBLIC_SUPABASE_URL=https://atrvkrxfcdtkoeyczjct.supabase.co
EXPO_PUBLIC_SUPABASE_ANON_KEY=<Supabase → Project Settings → API keys → publishable/anon key>
EXPO_PUBLIC_POWERSYNC_URL=<from A6>
EXPO_PUBLIC_API_URL=<Vercel URL from B6>
```
