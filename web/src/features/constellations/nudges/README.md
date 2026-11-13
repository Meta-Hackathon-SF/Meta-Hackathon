# nudges: event nudge card (owner: Adam)

`NudgeCard` renders one `EventNudge` (contracts/protocol.ts 2.0.0) inside a constellation chat. Kai's chat places it when a `muse_nudge` message carries a nudge.

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
