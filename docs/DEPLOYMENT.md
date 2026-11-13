# Hosting and deployment plan (Facebook Space)

Status: **deployed and partly verified (2026-11-13).** The "Live deployment" section below is what actually runs and was written by Adam after a live test run. Everything after it is Will's original plan from before the deploy; where the two differ, the live section is correct (web is on Vercel, API and Postgres are on Railway, not Supabase).

## Live deployment (verified 2026-11-13T15:05Z)

| Part | Where | How it deploys |
| --- | --- | --- |
| Web | Vercel project `constellations-demo`, https://constellations-demo-zeta.vercel.app | Every merge to `main`. Builds from the repo root `vercel.json`. PR previews are behind Vercel login, so they cannot be tested with curl or scripts. |
| API | Railway project `constellations-demo` (workspace "kai's Projects"), service `constellations-api`, region `sfo`, https://constellations-api-production.up.railway.app | Every merge to `main`. Builder is the repo `Dockerfile`; the start command lives in the Railway service settings. |
| Database | Railway `Postgres` (workflow) + a SQLite privacy file on a Railway volume (`CST_PRIVACY_DB`) | n/a |
| Muse | `api.meta.ai`, reached through the relay at `/api/muse/v1` on Vercel | Part of the web deploy (`api/_museRelay.js`) |

Request path: browser → Vercel `/api/v1/*` (rewrite) → Railway API → Vercel `/api/muse/v1/*` (relay function) → `api.meta.ai`.

Railway variables on `constellations-api`: `CONSTELLATIONS_ENV=production`, `CONSTELLATIONS_ALLOWED_ORIGINS=https://constellations-demo-zeta.vercel.app`, `CONSTELLATIONS_WORKFLOW_DSN`, `CST_PRIVACY_DB`, `CST_DEMO_HOST_SECRET`, `MUSE_API_KEY`, `MUSE_BASE_URL=https://constellations-demo-zeta.vercel.app/api/muse/v1`. `MUSE_MODEL` is unset; the per-task router (`server/providers/router.py`) picks models.

### What was verified live

In a real browser against the Vercel URL, with a synthetic test player holding the operator role (last run 2026-11-13T15:25Z to 15:35Z, cycle `cycle-b6db42065ac4…`):

| Step | Result |
| --- | --- |
| Join | 201 |
| Operator starts a week | 201; Monday question shown |
| Answer (M1 safety screen, M2 follow-up) | 202 in about 1 to 2 s; Muse live on `muse-ember-1.0` |
| Advance Monday to Friday | 200 each |
| Synthetic top-up (`POST /operator/cycles/{id}/synthetic-topup`) | 200; 38 labeled synthetic players and their answers |
| Lock and formation | Muse ran the whole job in about 10 s: 1 M3 and 1 M4 on `muse-ember-1.0`, 12 M5 and 2 M8 on `muse-wonder-1.0`, all `source: live` in `/operator/calls` |
| Reveal | 200 once the formation job had finished; cycle `revealed` |
| Sky (`GET /cycles/{id}/sky`) | 200: 38 eligible players, 12 constellations, 1 theme above threshold, 5 suppressed, live M8 headlines |
| Event stream (`GET /stream`) through the Vercel rewrite | 200 `text/event-stream`, events delivered |

**Not verified live:** sending a chat message in a real room, mutual reveal, the room event nudge, and the per-task `route_check --live` after the switch to the Vercel relay.

### Issues we hit, and what fixed them

1. **Railway was not deploying `main`.** Deploys were snapshots from one laptop (`railway up`), so merged PRs were not live. Fix: connected the service to the GitHub repo and committed the `Dockerfile` (#89). In the Railway UI a source change does nothing until you click **Apply**.
2. **Join failed on the live site ("unexpected error").** The web build calls the relative path `/api/v1`, but Vercel had no rule for it, so the calls hit the static site. The session cookie is `HttpOnly; Secure; SameSite=Lax; path=/api`, so the API must be same-site. Fix: the `/api/v1/:path*` rewrite to Railway in `vercel.json` (#91). Keep it above the SPA fallback.
3. **Every Muse call failed from Railway with `invalid_request`.** Cause: `api.meta.ai` returns an **empty model list** to our key when the request comes from Railway's IPs (`GET /models` 200 with `[]`, chat 404 `model_not_found`). The same key lists 10 models from a laptop and from Vercel. It is not the key (same SHA-256 on both sides), the code, the routes, or the region. Fix: the Vercel relay (#93). It forwards only `GET /v1/models` and `POST /v1/chat/completions`, only when the caller's bearer token hashes to our key (no key is stored in it), and logs nothing. If the key is rotated, update `KEY_SHA256` in `api/_museRelay.js`.
   - Our error label hid the cause: `invalid_request` covers 400, 404, 413 and 422. To see the provider's real message, run a small script in the container that prints the status and error body with the key redacted.
   - `python -m server.providers.route_check --live` in the container (about $0.01) checks every task end to end.
4. **Operator actions return 403 for a newly joined player.** By design the operator role is never granted over HTTP. Grant it in the container with `server.privacy.fixtures.grant_operator(PrivacyStore(os.environ["CST_PRIVACY_DB"]), "<playerId>", "facebook-space")`. The player ID comes from `GET /api/v1/session` in that browser. Each demo browser needs this once.
5. **A redeploy erases the current week.** Weeks live in `InMemoryCycleRepository` (`server/cycle/service.py`); players and sessions persist. Every merge to `main` and every Railway variable change redeploys. **Do not merge or change variables during the demo; start the demo week after the last deploy.** This happened twice during the 15:15Z test run (#99 and #100 merged mid-run). The workflow store (jobs, rooms, Sky, stream events) is in Postgres and does survive.
6. **`railway ssh` needs a registered key** (`railway ssh keys add`) and an interactive terminal for a passphrase-protected key; agents cannot run it. To run a script in the container without copying files: `railway ssh --service constellations-api -- sh -c "echo $(base64 < script.py | tr -d '\n') | base64 -d | python"`.
7. **`api/` on Vercel is ES modules** (`api/package.json` has `"type": "module"`). CommonJS `require` in a function there fails at load.
8. **Tracked `.pyc` files and a missing `.dockerignore`** made builds noisy; fixed in #89. `**/*.env` is excluded from the image, so secrets only come from Railway variables.

### Known gaps on the live site

- **The Space tab's Sunday screens are previews.** "Your constellation" and "Chat" in `web/src/features/constellations/daily/space/` show hardcoded "Preview · synthetic" content and make no server calls, even though the server has the real constellations, rooms and Sky. The real chat client exists (`web/src/features/constellations/chat/client.ts`) but the Space tab does not use it. This is the biggest gap between what the server does and what the demo shows.
- **"Skip to Sunday" stops with "The requested service is not available".** It asks for the reveal immediately after the lock, before the formation job (about 10 s) has finished, and the server answers 503. Wait a few seconds and press "Reveal (Sunday)". In the 15:25Z run the reveal still failed minutes later until an operator `POST /operator/cycles/{id}/form` was sent, which reported the job `succeeded`; whether the first job had failed is unknown because the server logs nothing for it. A proper fix is for the button to wait and retry while the cycle is `forming`.
- **"Skip to Sunday" adds no synthetic players on the live site.** Run the top-up yourself while the week is open and on Friday (it only fills days already reached, and needs a week created with demo timing).
- **Every non-GET request needs an `Idempotency-Key` header**, or the API answers 400 `INVALID_INPUT`. The web client adds it; hand-written `fetch`/curl calls must too.
- `GET /operator/cycles/{id}/formation-debug` returned 503 after a successful formation.
- The v3 per-viewer routes are not composed in `server/app/weekly.py`: `/days/{n}/constellations` returns 404, so after answering, the sky screen shows "0 people answered today".
- The server writes no request or error logs in production (`--no-access-log`, swallowed job errors), so failures can only be diagnosed through `/jobs/{id}`, `/operator/calls` and the API responses.
- Privacy `InterestBucket` uses `6-10`/`11+`; the contract and matching use `6-9`/`10+`.

## Original plan (pre-deploy, by Will)

The sections below are the plan as written before the deploy. They are kept for the reasoning about cookies and hosts.

## Decisions

| Part | Choice | Status |
| --- | --- | --- |
| Database (Kai's workflow schema) | **Supabase Postgres** | **Decided** |
| Web host (`web/`, React + Vite static build) | Open. Candidates: Vercel, Cloudflare Pages | Undecided |
| API host (FastAPI, `server/app/bootstrap.py`) | Open. Candidates: Render, Railway, Fly.io (any always-on container) | Undecided |
| Custom domain | Open | Undecided; it decides the cookie setup below |

## What each host must support

### Web host

Any static host works if it can do these three things:
- **Build:** root directory `web`, command `npm run build`, output `dist`, Node 22.12+.
- **SPA fallback:** deep links like `/space` and `/space/operator` must serve `index.html`, not a 404.
- **Build variable:** set `VITE_CONSTELLATIONS_API`. Without it the app runs in **fixture mode** (fake data, labeled), so production must set it.

If there's no custom domain, the web host must also **forward `/api/*` to the API host** (see Cookies).

How the candidates do this (verify at setup time):

| | Vercel | Cloudflare Pages |
| --- | --- | --- |
| SPA fallback | rewrite rule in `vercel.json` | automatic when there is no `404.html` |
| Forward `/api/*` | rewrite rule in `vercel.json` | needs a small Pages Function (`functions/api/[[path]].js`) that passes requests through; `_redirects` can't proxy to another server |

### API host

The API **can't run as serverless functions** (Vercel Functions, Cloudflare Workers or Pages Functions, Supabase Edge Functions):
- **Background work:** formation, Sky and nudge jobs run as an in-process worker (`asyncio.create_task(runtime.loop(...))`) with retries and leases. Serverless functions stop when the request ends.
- **Live updates:** chat uses Server-Sent Events, which hold connections open for minutes.
- **SQLite on local disk:** the privacy store is a SQLite file, so it needs a durable disk.
- **One process only:** the privacy publish guard and cycle serialization gate are process-local locks. Run exactly **one** instance, never autoscale.
- **Slow model calls:** formation can wait up to 120 s on Muse.

So the API host must offer:
- **An always-on container:** one instance, no sleeping and no autoscaling, Python 3.11.
- **A persistent volume** mounted at `/data` for `privacy.db`, with backups or snapshots.
- **Secrets** as environment variables.
- **A health check** on `/health/ready`.
- **Long-lived HTTP responses** for SSE.

**Install:** `pip install -r server/app/requirements-dev.lock && pip install --no-deps -e .`. Kai should split out a production lock without `pytest` and `ruff`.

**Start:**
```sh
uvicorn server.app.bootstrap:create_configured_app --factory --host 0.0.0.0 --port $PORT --workers 1 --no-access-log
```
Access logs stay off so query strings never reach logs. `/health/ready` returns 503 until privacy, the workflow database and every area are actually ready.

**Operator access:** granted only by a local setup function, never over HTTP (D007). Run it once through the host's shell for the demo operator account. The `facebook-space` play pool is seeded by `db/privacy/004_activity.sql` on first start.

## Cookies decide the URL setup

The session cookie is `cst_session`: `HttpOnly`, `Secure`, `SameSite=Lax`, `path=/api`. The browser only sends it when the web app and the API count as the **same site**. Two different platform domains (for example `*.vercel.app` and `*.onrender.com`) are different sites, so the cookie would be blocked. Pick one:

1. **Custom domain (recommended):** `app.<domain>` on the web host and `api.<domain>` on the API host. They are the same site, and live updates connect straight to the API.
   - Web: `VITE_CONSTELLATIONS_API=https://api.<domain>/api/v1`
   - API: `CONSTELLATIONS_ALLOWED_ORIGINS=https://app.<domain>`
2. **No custom domain:** the web host forwards `/api/*` to the API host, so everything comes from one site.
   - Web: `VITE_CONSTELLATIONS_API=/api/v1`
   - Test that live chat updates (SSE) stay open through the forwarding; if not, use option 1.

**If a proxy or CDN sits in front of `api.<domain>`** (for example Cloudflare's orange cloud), it may cut connections that stay silent too long (around 100 s on Cloudflare). Either the chat stream sends keep-alives more often than that, or the API record stays DNS-only. Whether Kai's stream sends keep-alives is not yet checked.

## Settings

Set these as secrets on each host and never commit them. `server/app/.env.example` and `server/providers/muse.env.example` are templates only.

**API host**

| Variable | Value |
| --- | --- |
| `CONSTELLATIONS_ENV` | `production` (turns off API docs, requires an explicit origin list) |
| `CONSTELLATIONS_ALLOWED_ORIGINS` | the web app's origin, no wildcard |
| `CONSTELLATIONS_WORKFLOW_DSN` | Supabase connection string for the app login role (below) |
| `CST_PRIVACY_DB` | `/data/privacy.db` on the persistent volume |
| `MUSE_API_KEY` | Muse key, server only |
| `MUSE_MODEL` | `muse-spark-1.3` (re-verify) |
| `MUSE_BASE_URL` | default `https://api.meta.ai/v1` |
| `CST_COOKIE_INSECURE_DEV` | **unset** (local http only) |

**Web host**

| Variable | Value |
| --- | --- |
| `VITE_CONSTELLATIONS_API` | `https://api.<domain>/api/v1` or `/api/v1` |

## Supabase setup (decided)

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
5. **Keep the Data API away from workflow tables.** Don't add the `workflow` schema to Supabase's exposed schemas. The tables already force RLS and grant nothing to `anon` or `authenticated`.
6. **Don't use Supabase Auth.** Sessions are Patrik's server-verified cookies (D007); a second auth system would confuse who is logged in.
7. **Turn on daily backups** (point-in-time recovery if the plan allows). Remember the 14-day retention rule: backups must not quietly keep deleted answers much longer than that.
8. **Free plan:** it pauses inactive projects. Fine for a demo; a weekly game that must wake up on Saturday needs a paid plan.

**Later (optional):** move the privacy store from SQLite into this Supabase database. That's a D007 change for Patrik, and it removes the need for a volume on the API host.

## What must land before a real deploy

Status as of 2026-11-13. Most items are code work, not hosting work.

1. **Kai's PR #13 merged.** It contains the composed app, the worker, chat, reveal and SSE. Main has no runnable full server without it.
2. **Will's matching fix.** Matching currently adds the private fields `closeness` and `memberContext` to its output, and Kai's strict checks reject them. Kai's end-to-end test fails when #13 is combined with main. Fix: keep them on the result object but out of the output Kai checks; Kai then moves his checks to 2.1.0.
3. **Will's durable cycle state.** Weekly-cycle state and the follow-up cache are in memory, so a restart loses the current week. They need to live in Postgres (Kai's migration order) or the privacy store.
4. **Will mounts Kai's chat UI** (`LiveConstellation`) on `/space` so players can chat and reveal.
5. **A production lock file** without dev tools (Kai).
6. **Choose the web host, API host and domain** (table above).
7. **One full rehearsal on the deployed stack:**
   - with the real Muse key;
   - 3+ test players on phones;
   - through join → answers → lock → formation → reveal → chat → mutual reveal.

   Nobody has done this yet.

## Deploy steps (once the list above is done)

1. **Supabase:** create the project, run the migrations, create `cst_app`, copy the session-pooler connection string.
2. **API host:** create the service and volume, set the variables, deploy, and wait for `/health/ready` to return 200.
3. **Grant the operator** once through the host shell.
4. **Web host:** connect the repo with root `web`, build `npm run build`, output `dist`. Set up the SPA fallback (and `/api` forwarding if there's no custom domain), and set `VITE_CONSTELLATIONS_API`.
5. **DNS** (custom domain): `app.<domain>` → web host, `api.<domain>` → API host.
6. **Smoke test on a phone:**
   - The page shows **no** "Fixture mode" label.
   - Join → the cookie is set.
   - Answer → reload → the answer is still there.
   - The operator console loads.
   - Advance to the reveal → a room opens.
   - A chat message arrives live on a second phone.
   - Restart the API → state survives.
7. **Rollback:** redeploy the previous web build and API image. Database migrations are forward-only, so take a Supabase backup before each migration.

## Costs

The API host must not sleep: free tiers that spin down stop formation jobs and drop live chat. Budget for the smallest always-on plan. Check current pricing on each provider's site; this file makes no pricing claims.
