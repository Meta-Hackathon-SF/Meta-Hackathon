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
