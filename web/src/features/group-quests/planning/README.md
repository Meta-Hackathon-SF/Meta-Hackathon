# Planning UI (owner: Adam)

Status: **components implemented, fixture-previewed only**. They are not routed yet (Will owns the route and composition) and not yet connected to a live backend.

Import from `features/group-quests/planning` (the `index.ts`). Styling uses Tailwind utilities only: no global selectors and no shell CSS changes. All components are presentational: they make no network calls, and the parent passes data and callbacks.

## Components and props
| Component | Key props | Notes |
| --- | --- | --- |
| `PlanProposalCard` | `plan: PublicPlanCard`, `phase: "joining" \| "confirming_plan" \| "reconfirming" \| "confirmed"`, `previous?`, `revisionReason?`, `acceptedCount?`, `minimumSize=3`, `capacity=5`, `viewerChoice?`, `onAccept?`, `onDecline?`, `busy?`, `error?` | Button text depends on the phase, so joining a quest and confirming a plan look different (WORKFLOW.md). Passing `previous` shows a `RevisionDiff`. |
| `RevisionDiff` | `previous`, `current`, `reason?` | A before/after comparison. A change to time, place or cost is shown as requiring reconfirmation. |
| `PlanStatusPanel` | `state: PlanStatusState`, `onRetry?`, `onProvideInput?`, `onAdjust?` | Covers four states: planning, `needs_input`, `no_feasible_plan` (says limits are never loosened), and error (retry only shown when `retryable`). |
| `ContinuationCard` | `continuation: Continuation`, `simulated`, `viewerId`, `hostName?`, `onAcceptHost?(draft)`, `hostAccepted?`, `busy?`, `error?` | Shows a time-skip banner when `simulated`. Only the proposed host sees the editable draft and the accept button. Accepting saves a draft only and sends nothing. |
| `EvidenceBadge` | `evidence: ModelEvidence` | Shows Live, Replay or Fixture. A `fixture:` model prefix is treated as fixture until D005 lands. |

`PublicPlanCard` (in `types.ts`) is the allowlisted projection of `QuestPlan` with its venue resolved. It drops `memberVersions` and `opener`; the opener arrives as an assistant chat message from Kai. **Patrik: please ACK or adjust this as the public plan DTO.**

## Client helpers
- `extractIntent({ baseUrl, transcript, communityId, signal })` calls `POST /intents/extract` with `credentials: "include"`, then validates the response with `parseExtractionResult` before returning it (D005 shape).
- `createLatestOnly()` handles overlapping requests: starting a new request aborts the previous one, and a superseded request's result comes back as `{ stale: true }` rather than being applied. Will can use it for re-extraction after edits.
- `PlanningApiError` carries `code`, `retryable` and `requestId` from the ApiError envelope.

## Preview (dev only, synthetic fixtures)
```sh
cd web && npm run dev
# open /src/features/group-quests/planning/preview/index.html
```
The preview is excluded from production builds, because only `web/index.html` is a build entry. Everything it shows is labeled fixture.
