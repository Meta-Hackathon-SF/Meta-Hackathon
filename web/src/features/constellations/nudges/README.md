# nudges: event nudge card (owner: Adam)

`NudgeCard` renders one `EventNudge` (contracts/protocol.ts 2.0.0) inside a constellation chat. Players' chat receives only `ChatMessage {text, kind: "muse_nudge"}` (no nudge fields), so in chat the nudge shows as a Muse text bubble; the full card is for the operator view below, or for chat if a future contract adds nudge data to the message.

```tsx
import { NudgeCard, parseEventNudge, parseVenue } from '../nudges'

const nudge = parseEventNudge(payload)   // null unless it matches the contract exactly
const venue = parseVenue(venuePayload)   // null unless isPublic is true
{nudge && <NudgeCard nudge={nudge} venue={venue} timeZone={communityTimeZone} />}
```

- The card renders nothing without an approved public venue whose `placeId` matches the nudge.
- A nudge whose evidence says `source: "replay"` always shows "Replay of a saved cycle".
- `showEvidence` adds call type, model and latency for operator views.
- Status: built, type-checked and viewed once in Chrome at 360 px and 900 px through a temporary preview page (live and replay variants, long title, no horizontal overflow, invalid nudge parsed to null). Not mounted on any route, no committed browser test, not yet seen inside the chat or with server data.

## Operator demo button: `OperatorNudgePanel`

```tsx
import { OperatorNudgePanel, createNudgeRequester } from '../nudges'

<OperatorNudgePanel roomId={openRoomId} request={createNudgeRequester(apiBase)} timeZone={communityTimeZone} />
```

- Calls `POST /operator/rooms/:id/nudge` (contracts/API.md) with the session cookie and an `Idempotency-Key`; never sends a playerId. The server checks the operator role.
- The response is validated with `parseEventNudge`; the venue must be on `APPROVED_VENUES` (`venues.ts`, a copy of `server/planning/data/venues.json`; `tests/planning/test_web_venues.py` fails on drift). Otherwise nothing is shown.
- Errors show code-chosen messages only (`NOT_FOUND`, `PROVIDER_UNAVAILABLE`, ...), never the server's free text. Unmount or a new `roomId` cancels the call in flight and drops its result; the button is disabled while busy.
- Status: viewed in Chrome via a temporary uncommitted preview with a stubbed requester (posted at 360/900 px, provider failure, non-allowlisted venue, cancel on reload; no overflow, no page errors). Not mounted on any route; not run against the server, which needs Kai to pass `NudgeService` into `PlanningRuntime`.
