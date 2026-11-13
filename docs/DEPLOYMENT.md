# Hosting and deployment plan (Facebook Space)

Status: **plan only. Nothing is deployed.** Proposed by Will on 2026-11-13. Kai owns server manifests and migration order (D002) and Patrik owns the privacy store (D007), so both review this before anything goes live. Delete or update this file once a real deployment is verified.

## Verdict: Vercel + Supabase works, with one extra piece

| Part | Where | Works? | Why |
| --- | --- | --- | --- |
| Web app (`web/`, React + Vite) | **Vercel** | Yes | Static build, SPA routing, preview deploys per PR. |
| Workflow database (Kai's `db/workflow`) | **Supabase Postgres** | Yes | Plain PostgreSQL with roles and RLS. |
| API server (FastAPI, `server/app/bootstrap.py`) | **Not Vercel.** An always-on container host: Render, Railway or Fly.io | Vercel functions: **no** | See below. |
| Privacy store (Patrik's SQLite, D007) | A persistent disk on the API host | Yes, with a volume | Vercel and most serverless hosts have no durable disk. |
| Muse model | Meta's API, called only by the API server | Yes | The key lives only on the API host. |

**Why the API can't run on Vercel functions:**
- **Background work:** formation, Sky and nudge jobs run as an in-process worker (`asyncio.create_task(runtime.loop(...))`) with retries and leases. Serverless functions stop when the request ends.
- **Live updates:** chat uses Server-Sent Events, which hold a connection open for minutes. Vercel functions have execution time limits.
- **SQLite on local disk:** the privacy store is a SQLite file. Function file systems are temporary.
- **One process only:** the privacy publish guard and the cycle serialization gate are process-local locks. Running two copies at once would break the "nothing changes between check and commit" guarantee. Run exactly one instance, never autoscale.
- **Slow model calls:** formation can wait up to 120 s on Muse.

Supabase Edge Functions have the same limits. The fix is one small always-on container for the API (paid tier, so it never sleeps and drops jobs or streams).

## Target layout

```text
Browser ──► app.<domain>  (Vercel: static web build)
   │
   └──► /api/*  ──►  API host (one container, one process)
                       uvicorn server.app.bootstrap:create_configured_app --factory
                       ├─ privacy SQLite on a persistent volume  (/data/privacy.db)
                       ├─ Supabase Postgres  (workflow schema, RLS, workflow_runtime role)
                       └─ Muse API (server-only key)
```

### Cookies decide the URL setup

The session cookie is `cst_session`: `HttpOnly`, `Secure`, `SameSite=Lax`, `path=/api`. The browser only sends it if the web app and API count as the **same site**. `*.vercel.app` and `*.onrender.com` are different sites, so the cookie would be blocked. Pick one:

1. **Custom domain (recommended):** `app.<domain>` on Vercel and `api.<domain>` on the API host. They are the same site, so the cookie works, and live updates connect directly to the API.
   - Web: `VITE_CONSTELLATIONS_API=https://api.<domain>/api/v1`
   - API: `CONSTELLATIONS_ALLOWED_ORIGINS=https://app.<domain>`
2. **No custom domain:** a Vercel rewrite proxies `/api/*` to the API host, so everything appears to come from the Vercel URL.
   - Web: `VITE_CONSTELLATIONS_API=/api/v1`
   - Verify during setup that live chat updates (SSE) stay open through the rewrite. If they get cut off, switch to option 1.

`web/vercel.json` for option 2 (option 1 only needs the second rule):

```json
{
  "rewrites": [
    { "source": "/api/:path*", "destination": "https://<api-host>/api/:path*" },
    { "source": "/((?!api/).*)", "destination": "/index.html" }
  ]
}
```

The second rule makes deep links like `/space` and `/space/operator` load the app instead of a 404.

## Settings

Set these as environment variables or secrets on each host. Never commit them. `server/app/.env.example` and `server/providers/muse.env.example` are templates only.

**API host**

| Variable | Value |
| --- | --- |
| `CONSTELLATIONS_ENV` | `production` (turns off API docs and requires an explicit origin list) |
| `CONSTELLATIONS_ALLOWED_ORIGINS` | `https://app.<domain>` (no wildcard) |
| `CONSTELLATIONS_WORKFLOW_DSN` | Supabase connection string for the app login role (see below) |
| `CST_PRIVACY_DB` | `/data/privacy.db` on the persistent volume |
| `MUSE_API_KEY` | Muse key, server only |
| `MUSE_MODEL` | `muse-spark-1.3` (re-verify) |
| `MUSE_BASE_URL` | default `https://api.meta.ai/v1` |
| `CST_COOKIE_INSECURE_DEV` | **unset** (only for local http) |

**Vercel (web)**

| Variable | Value |
| --- | --- |
| `VITE_CONSTELLATIONS_API` | `https://api.<domain>/api/v1` or `/api/v1` |

Without `VITE_CONSTELLATIONS_API` the web app runs in **fixture mode** (fake data, labeled). Production must set it, or players would play against the browser fixture.

## Supabase setup

1. **Create a project** in the region closest to the API host.
2. **Run the migrations** in order with the SQL editor or `psql`. Kai's migrations target a fresh database:
   - `db/workflow/001_workflow.sql`
   - `db/workflow/002_runtime_state.sql`
3. **Create the login role the API uses.** It must inherit `workflow_runtime`:
   ```sql
   CREATE ROLE cst_app LOGIN PASSWORD '<generated, stored only in the API host secret>';
   GRANT workflow_runtime TO cst_app;
   ```
4. **Connect through the session pooler**, port 5432 (IPv4 friendly). Avoid the transaction pooler: the repository uses `SELECT … FOR UPDATE` inside transactions.
5. **Keep the Data API away from workflow tables.** Do not add the `workflow` schema to Supabase's exposed schemas. The tables already have RLS forced and no grants to `anon` or `authenticated`.
6. **Don't use Supabase Auth.** Sessions are Patrik's server-verified cookies (D007). A second auth system would confuse who is logged in.
7. **Turn on daily backups** (point-in-time recovery if the plan allows). Remember the 14-day retention rule: the app deletes answers; backups must not quietly keep them much longer than that.

**Later (optional):** move the privacy store from SQLite into this Supabase database. That's a D007 change for Patrik and removes the need for a volume.

## API host setup (Render, Railway or Fly.io)

- **Machine:** one service, **one instance, autoscaling off**, Python 3.11, smallest always-on paid size.
- **Volume:** a persistent volume mounted at `/data` for `privacy.db`, with backups or snapshots on.
- **Install:** `pip install -r server/app/requirements-dev.lock && pip install --no-deps -e .`
  Kai should split out a production lock without `pytest` and `ruff`.
- **Start:**
  ```sh
  uvicorn server.app.bootstrap:create_configured_app --factory --host 0.0.0.0 --port $PORT --workers 1 --no-access-log
  ```
  Access logs stay off so query strings never reach logs.
- **Health check:** `/health/ready`. It returns 503 until privacy, the workflow database and every area are actually ready, so a bad deploy never takes traffic.
- **Operator access:** granted only by a local setup function, never over HTTP (D007). Run it once through the host's shell for the demo operator account.
- **Demo pool:** the `facebook-space` pool is seeded by `db/privacy/004_activity.sql` on first start.

## What must land before a real deploy

Status as of 2026-11-13. Most items are code work, not hosting work.

1. **Kai's PR #13 merged.** It contains the composed app, the worker, chat, reveal and SSE. Main has no runnable full server without it.
2. **Will's matching fix.** Matching currently adds the private fields `closeness` and `memberContext` to its output, and Kai's strict checks reject them. Kai's end-to-end test fails when #13 is combined with main. Fix: keep them on the result object but out of the output Kai checks; Kai then moves his checks to 2.1.0.
3. **Will's durable cycle state.** Weekly-cycle state and the follow-up cache are in memory, so a restart loses the current week. They need to live in Postgres (Kai's migration order) or the privacy store.
4. **Will mounts Kai's chat UI** (`LiveConstellation`) on `/space` so players can chat and reveal.
5. **A production lock file** without dev tools (Kai).
6. **One full rehearsal on the deployed stack:**
   - with the real Muse key;
   - 3+ test players on phones;
   - through join → answers → lock → formation → reveal → chat → mutual reveal.

   Nobody has done this yet.

## Deploy steps (once the list above is done)

1. **Supabase:** create the project, run the migrations, create `cst_app`, copy the session-pooler connection string.
2. **API host:** create the service and volume, set the variables, deploy, and wait for `/health/ready` to return 200.
3. **Grant the operator** once through the host shell.
4. **Vercel:** import the repo with root directory `web`, build `npm run build`, output `dist`. Add `vercel.json` and set `VITE_CONSTELLATIONS_API`.
5. **DNS** (option 1): `app.<domain>` → Vercel, `api.<domain>` → API host.
6. **Smoke test on a phone:**
   - The page shows **no** "Fixture mode" label.
   - Join → the cookie is set.
   - Answer → reload → the answer is still there.
   - The operator console loads.
   - Advance to the reveal → a room opens.
   - A chat message arrives live on a second phone.
   - Restart the API → state survives.
7. **Rollback:** Vercel "promote previous deployment"; the API host redeploys the previous image. Database migrations are forward-only, so take a Supabase backup before each migration.

## Costs and limits to check before choosing

- **Vercel Hobby** is for non-commercial use; fine for a hackathon demo.
- **Supabase Free** pauses inactive projects. Fine for a demo, not for a weekly game that must wake up on Saturday.
- **The API host must not sleep.** Free tiers on Render and Railway spin down, which stops formation jobs and drops live chat updates. Budget for the smallest always-on plan.

Check current pricing on each provider's site; this file makes no pricing claims.
