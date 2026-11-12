# Privacy UI (Patrik)

These components cover sessions, consent, the public/private preview and leaving a community. They're scoped with `privacy.module.css`, so no global selectors change, and they don't depend on the mock shell's users or localStorage.

## Mount (Will's shell)
```tsx
import { PrivacyCenter, httpPrivacyClient } from "../privacy";
const client = httpPrivacyClient("/api/v1"); // create once
<PrivacyCenter client={client} communityId="demo-campus" communityName="Demo Campus"
  onMatchableChange={setMatchable} />
```
- `onMatchableChange(boolean)` is true only when matching **and** Muse processing are on. Use it to enable "Find my group".
- The dev server needs a proxy from `/api` to the backend; Will/Kai own `vite.config.ts`. The session cookie is HttpOnly on path `/api`, so same-origin requests are required.
- `fixturePrivacyClient()` is in-memory, for UI work only. Everything it renders carries a visible **Fixture mode** badge, and it provides no authentication.

## Exports
| Export | Props / purpose |
| --- | --- |
| `PrivacyCenter` | `{client, communityId, communityName, onMatchableChange?}`. Covers the full flow, including loading, error/retry, signed-out, join, consent, preview and leave. |
| `JoinCommunityCard` | `{client, communityId, communityName, onJoined(membership)}`. All toggles start **off**; it can't be submitted without a display name. |
| `ConsentPanel` | `{client, membership, onSaved?(consent), onStale?()}`. Saves with `expectedVersion`. A 409 STALE_REVISION shows a notice and calls `onStale` to reload. Withdrawing shows an immediate-effect warning. Remount it with `key={consent.version}` after reload. |
| `PublicPreview` | `{displayName, consent, intent?}`. Shows "Your group sees" next to "Only you see". |
| `LeaveCommunity` | `{client, communityId, communityName, onLeft(consent)}`. A two-step confirm; leaving withdraws all consent and deletes the private intent server-side. |
| `MatchableStatus`, `ConsentToggleList`, `FixtureBadge` | Building blocks. |
| `usePrivacySession(client)` | `{state: loading/signed_out/ready/error, reload, start}`. Superseded loads are aborted and ignored. |
| `httpPrivacyClient`, `fixturePrivacyClient`, `PrivacyApiError` | Clients and a typed error carrying `code`, `requestId` and `retryable`. |

Wire types (`Consent`, `PrivateIntent`) are imported from `contracts/protocol.ts`; the session/membership DTOs follow docs/DECISIONS.md D007.

## Accessibility
- Toggles are `role="switch"` buttons with `aria-checked` and a described-by detail.
- Status messages use `role="status"`; errors use `role="alert"`.
- Everything works by keyboard, with visible focus rings.
- The layout collapses to one column below 560px.
