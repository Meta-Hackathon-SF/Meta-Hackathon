# Chat and Sky handoff (Kai)

`ChatPanel` and `SkyPanel` are independent React components; Will owns Groups
routing and can import them from the corresponding index.ts. No shell file or
route has been changed. Every public wire type is imported from protocol.ts.
Runtime validators reject extra/private fields, coercion and invalid numbers.

Chat actions are injected callbacks, not fake HTTP success. An unconnected panel
has disabled controls. The production parent must provide server-verified room,
moderated messages, private pair-only mutual-reveal events and model evidence.
It must update messages on `chat.moderated` and stop/reload on consent/expiry.
Per-room component remount cancels stale work; retries reuse the same action key.
Names appear from validated MutualReveal only, never from a pending/revealed
HTTP acknowledgement alone. Never pass an unfiltered community event stream.

Muse chat texts require supplied MuseCallEvidence in live mode; without evidence
they stay hidden. `nudgeSlot` is a ReactNode for Adam's approved NudgeCard (step 6,
cuttable), not a new data shape. Sky uses Rishi's numbers without recomputing them,
filters count < threshold and suppresses all headlines if a malformed low-count
theme arrived. Every synthetic signal is visibly separate and labeled.

The TEST-ONLY preview and adapters under chat/test-only/ are never imported by
the application entrypoint. Vite serves that HTML only in development:
`/src/features/constellations/chat/test-only/index.html`. It reads the shared
chat-room.json and sky-stats.json, labels all synthetic content, simulates no real
session and makes no model call. Its contact filter is a UI test double, not the
production OutputGuard. Test controls are outside the exported product component.

Preview: `npm run dev -- --host 127.0.0.1 --port 5193` from web/.
Targeted browser checks (with the preview running):
`npx playwright test --config src/features/constellations/chat/test-only/playwright.config.ts`.
Also run the role's normal lint/build/test:e2e before declaring the PR ready.

## Live adapter and container

Will can import `LiveConstellation` from this directory's index.ts and mount it
inside the existing server-backed privacy gate. Props are `cycleId`, `viewerPlayerId` from the verified own-session, optional
`baseUrl` (default `/api/v1`), `messageEvidence`, `nudgeSlot`, `projector` and `demoTiming`.
Pass demoTiming from the verified WeeklyCycle to show the Demo timing notice.
The container keys its memory by that viewer and cycle. viewerPlayerId is used
only to reject mutual-reveal events for another pair, never sent as identity;
HTTP authentication still comes solely from the server session cookie.
This export does not alter Groups routing or authenticate a viewer itself.

`createChatClient` uses credentialed HTTP with runtime validators. Every mutation
sends the action's stable Idempotency-Key. It never sends playerId or a fixture
override. The fetch-based SSE reader uses Last-Event-ID, validates seq/id/type,
drops duplicates, handles split chunks/CRLF and reconnects with bounded backoff.
Events are processed in order so an authorized room refresh completes before
replayed identities are considered. Mismatched-room messages/reveals are ignored.
The server remains responsible for mutual-pair recipient authorization.

Room, messages and Sky are fetched from their existing contract routes; report
and block callbacks update the local view after the server responds. Moderation
events hide messages immediately and refresh the canonical projection. Auth or
consent loss clears the view, expiry disables writes, and cycle changes abort
stale requests. Pending reveal responses never create identities. Muse text
without supplied model evidence stays hidden in live mode. No session content
or chat text is written to localStorage or logs.

`test-only/live.html` is a separate HTTP-intercept test harness, explicitly
synthetic and never imported by the application entrypoint. `live.spec.ts` and
`client.spec.ts` prove adapter/browser mechanics; no backend, paid model, real
participant or physical-phone verification is claimed.
