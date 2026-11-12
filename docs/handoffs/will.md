# will handoff
```text
Current phase: P1 complete with fixture evidence; P2 (live wiring) blocked on upstream endpoints
Status: verified (fixture only); not live-integrated
Branch + commit: role/will-voice-ui @ ab59138 (base main a9241f1)
Shared contract: 1.0.0 (no contract changes)
```

## Completed deliverables
- **P0 route plan:** the feature route `/groups/:communityId/quests` is registered under the existing `AppLayout` in `web/src/App.tsx`. Each Groups card in the mock shell has a "Group Quests" entry link. No other shell routes, feed or global CSS changed.
- **P1 onboarding** (`web/src/features/group-quests/onboarding/`): the voice note path and the typed path both lead to an editable transcript, then extraction, then editable fields, then a confirmed intent.
  - Missing required fields (goal, interests, area, availability, budget, max duration) each get an explicit question. No value is ever filled in by default.
  - Runtime validators run on extraction responses, `PrivateIntent` responses and the outgoing submission.
  - Stale responses are guarded: every request carries a sequence number and an `AbortController`, so a cancelled or superseded result is discarded.
  - Errors are retryable where the server says so. A "fill in details myself" path is always available.
  - Retrying the same body reuses the same `Idempotency-Key`; a changed body gets a new key.
  - Fully keyboard-operable, with focus management and a live status region.
- **Feature shell** (`web/src/features/group-quests/shell/`):
  - Page composition with visible mode labels.
  - A fixture-only consent stand-in.
  - The first-action timer: it starts on the server-acknowledged confirmed intent, completes only through the events slot's `onAccepted`, and records abandoned attempts separately.
  - Typed component slots for the other owners.
- **`server/voice/`:** framework-independent `transcribe_audio()` that validates the upload's type, size and container signature.
  - Provider errors are sanitized into `ApiError` codes.
  - `UnconfiguredTranscriber` is the honest 503 default; `FixtureTranscriber` is for tests only.

## Fixture versus live evidence
Everything below ran against the **fixture adapter**: keyword rules, a canned transcript and an in-memory save. Muse, speech-to-text and the server were not involved. This proves UI behavior only, not live integration. The live HTTP adapter (`httpAdapter.ts`) has typechecked and built but has **not** been run against a server.

## Checks run (2026-11-12, macOS, Node 24.11.1, Python 3.11.9)
| Command (cwd) | Result |
| --- | --- |
| `npx tsc -b` (web) | pass |
| `npm run lint` (web) | pass, 0 warnings |
| `npm run build` (web) | pass |
| `npx playwright test` (web) | 36/36 pass: 16 existing feed tests and 20 new onboarding tests, across the desktop and mobile projects |
| `python3 -m unittest discover -s tests/onboarding -v` (root) | 10/10 pass |

The new Playwright specs (`web/tests/group-quests-onboarding.spec.ts`) cover:
- shell entry and labels;
- no submission before consent;
- the full keyboard flow;
- a correction changing the submitted intent;
- explicit missing-availability questions;
- a cancelled extraction that returns late without overwriting the corrected text;
- provider failure with retry and the manual path;
- microphone denied;
- unsupported browser;
- voice to fixture transcript;
- no horizontal overflow on mobile;
- a timer that cannot complete without acceptance;
- editing an intent bumps its version and abandons the timer attempt.

## Interfaces published (for ACK)
**To Patrik: confirmed intent payload for `PUT /api/v1/intents/me`.** It is `ConfirmedIntentSubmission` in `onboarding/types.ts`: the `PrivateIntent` fields `communityId, goal, interests, areaId, timeZone, availability, maxBudgetMinor, currency, maxDurationMinutes, groupPreference`, plus `expectedVersion` (0 = none yet).
- `participantId`, `intentVersion`, `consentVersion` and `confirmedAt` are left to the server; the session supplies identity.
- The response is validated as `PrivateIntent`.
- Mutations send `Idempotency-Key` and `credentials: "include"`.
- Please confirm that `expectedVersion: 0` is right for a first save.

**To Adam: extraction UX requirements for `POST /api/v1/intents/extract`.**
- Expected response: `{ draft: Partial<PrivateIntent subset>, missingFields: IntentField[], evidence?: ModelEvidence }`.
- `IntentField` is one of `goal | interests | areaId | availability | maxBudgetMinor | maxDurationMinutes`.
- Leave a field absent when it's unknown. Never guess availability, area or budget.
- `draft.currency`, if present, must equal the community currency; otherwise the budget is ignored.
- `evidence.model` and `source` are displayed.
- **Contract gap:** `protocol.ts` has no draft/extraction type. I derived it locally from `PrivateIntent` and did not change the contract. Please add a shared `IntentExtraction` type through DECISIONS.md, or ACK this shape.

**To Kai:**
- Onboarding treats `202` as unsupported. Tell me if extraction or transcription will be async jobs, and confirm the `GET /jobs/:id` body shape.
- `server/voice.transcribe_audio(content_type, data, transcriber, request_id=...)` is ready for you to register at `POST /voice/transcribe`. Use `VoiceError.to_api_error()` for errors.
- Please supply the mode (`live` / `fixture` / `replay`) from the server. Right now `VITE_GQ_API_BASE` set means "live" (TODO P2).

**To every UI owner: component slot contract** (`shell/slots.ts`). Export your component and register it in `featureSlots` with a one-line PR.
- `privacy` (Patrik): `{communityId, mode, onConsentChange(Consent|null)}`. Onboarding is enabled only when `matching && modelProcessing && revokedAt === null`.
- `matching` (Rishi): `{communityId, mode, confirmedIntentVersion, onQuestCreated(questId)}`
- `planning` (Adam): `{communityId, mode, questId}`
- `events` (Kai): `{communityId, mode, questId, onAccepted({questId, revision, acceptedAt})}`. Call it only after the server acknowledges a persisted acceptance.

An empty slot renders "Not integrated", never a fake result. Request prop changes here.

## Shared files touched (Will coordinates web routing)
- `web/src/App.tsx`: one route.
- `web/src/pages/SecondaryPages.tsx`: entry link on the Groups cards.
- `web/src/components/navigation/Header.tsx` and `web/src/layouts/AppLayout.tsx`: the "Group Quests" title for the new route.
- No package or manifest changes.

## Blocked on
- Patrik: session/consent API and component.
- Adam: extraction endpoint and an ACK of the shape.
- Kai: server composition and the route for voice.
- Rishi/Kai: matching and events components.
- H0 decision: a speech-to-text provider. Muse audio support is unverified, so voice currently falls back to typing.

## Next consumer action
Patrik and Adam ACK or amend the two payloads above. Every owner exposes a slot component.

## Next independent task
P3 resilience that doesn't need upstream:
- recovery when a session expires mid-flow;
- reconnect/retry UX;
- persisting an unsent draft per viewer.

Then wire the real ports as each one lands (P2).
