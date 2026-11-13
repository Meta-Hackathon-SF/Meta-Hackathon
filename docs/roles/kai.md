# Kai: anonymous chat, expiration, mutual reveal, realtime, API composition, Sky UI
Branch `role/kai-orchestration` · Handle `@beatopia` · Build order steps 2, 5, 8

## You own
| Path | What |
| --- | --- |
| `server/app/` | FastAPI app, config, registry, middleware, envelope, idempotency, `/health`, mounting every owner's router, migration order, `pyproject.toml` |
| `server/orchestration/` | job worker (formation job at lock), Sunday reveal (open rooms, assign anonymous handles), SSE stream with seq + replay |
| `server/chat/` | ChatPort, rooms, messages, rate limits, report and block flow (calls Patrik for screening and storage), expiry, mutual reveal |
| `tests/orchestration/`, `tests/chat/` | tests incl. concurrency |
| `web/src/features/constellations/chat/` | reveal card, anonymous chat, report/block menu, reveal request, expiry banner, nudge slot (Adam's card) |
| `web/src/features/constellations/sky/` | Sky UI: projector + phone view of SkyStats (themes, guessed vs actual, constellations, mutual reveals, "Synthetic signal" labels, Muse chip) |

Not yours: SkyStats numbers (Rishi computes), moderation decisions (Patrik), cycle timing (Will).

## Interfaces
Produce: `ChatPort`, `ChatRoom`, `AnonymousHandle`, `ChatMessage`, `RevealRequest`, `MutualReveal`, `StreamEvent`, app registry convention, routes under "Chat" and "Formation and Sky" in contracts/API.md.
Consume: `FormationPort.form/computeSky` (Rishi), `PrivacyPort` + `OutputGuard` + report store (Patrik), `CyclePort` (Will), `NudgePort` (Adam).

## Tasks
1. Restore `server/app/*`, `server/orchestration/*`, `pyproject.toml`, `.github/workflows/validation.yml`, `db/workflow/*` from `archive/group-quests-before-pivot`; rename, adapt to 2.0.0, retest. Publish registry convention so others can mount routers on day one.
2. Formation job at lock (call Rishi), commit, Sunday reveal publishing.
3. Rooms + anonymous handles + messages + moderation pipeline + rate limit.
4. Report, block, expiry (read-only then TTL), mutual reveal transaction.
5. SSE with seq and Last-Event-ID replay, per-player filtering.
6. Chat UI and Sky UI against `chat-room.json` and `sky-stats.json` first, then live.

## Acceptance checks
- `pytest tests/orchestration tests/chat` green; web lint/build green.
- Message to expired room returns `ROOM_EXPIRED`; one-sided reveal returns `pending` and leaks nothing; duplicate reveal idempotent.
- Reported message disappears for reporter immediately; 2 reports auto-hide.
- SSE reconnect replays missed events by seq; no event reaches a non-member.
- Sky UI never shows a theme below threshold and labels every synthetic signal.
