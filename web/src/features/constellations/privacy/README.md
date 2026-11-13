# Facebook Space privacy UI (owner: Patrik)

Role task 7: the join and consent screen (three toggles), privacy settings with "delete my data", and the private support card. Styles use the `.cstp-` prefix only, so the Simulated Facebook shell, the feed and Will's `.cst-` styles are untouched.

## Mount (Will owns `App.tsx` and `DailyPage`)
Wrap the daily page so a player sees the join screen until this Group's session exists with all three consents:
```tsx
import { getPrivacyClient, PrivacyGate } from "../privacy";

<PrivacyGate client={getPrivacyClient()} communityId={communityId} communityName={COMMUNITIES[communityId]}>
  <DailyPage />
</PrivacyGate>
```
- **Signed out or not a member:** `JoinScreen` shows what only the player sees next to what others see, a display name, and three switches that all start off. Join is disabled until all three are on.
- **Joined but any toggle off:** "Paused" settings only, so the daily page is hidden. Withdrawing takes effect immediately on the server.
- **Fully consented:** the children render, followed by a collapsible "Privacy and data" panel (consent switches, delete my answers and guesses, sign out). Pass `onDataDeleted` to refresh the page after a delete.
- `SupportCard` is the private card for a flagged answer (campus counseling, 988, 911). It never counsels. It can replace the inline card in `DailyPage`.

## Modes
`getPrivacyClient()` uses the same switch as the daily page:
- **Live:** `VITE_CONSTELLATIONS_API` (for example `/api/v1`). Calls `POST /communities/:id/join`, `GET`/`DELETE /session`, `PATCH /me/consent` and `DELETE /me/data`, with cookie credentials and an `Idempotency-Key` on every mutation. It never sends a playerId.
- **Fixture:** without the env var. One synthetic player per tab in `sessionStorage`, with no authentication. Every screen shows **Fixture mode**.

Every server response is validated at runtime (`parseSession`, `parseConsent`). A malformed response is an error, never trusted data.

## Verified (2026-11-13)
- `npm run lint`: no findings in this folder. `tsc -b` and `npm run build` pass.
- A Playwright flow, run against a temporary local mount (not committed, because `App.tsx` is Will's), passes on desktop and mobile:
  - join stays disabled until all three toggles are on;
  - the switches work by keyboard;
  - the daily page appears after joining and survives a reload;
  - withdrawing a toggle pauses play and hides the daily page;
  - turning it back on restores the page;
  - delete my data and sign out work;
  - the 988 link is `tel:988`.
- Existing browser tests: 32 passed.
- Live mode against the real server was not run in a browser. The server side is covered by `tests/privacy`.

## Accessibility
- Switches are `role="switch"` buttons with `aria-checked` and an `aria-describedby` detail.
- Statuses use `role="status"` and errors use `role="alert"`.
- Focus rings are visible, and touch targets are at least 44px.
- The private/shared columns stack below 560px.
