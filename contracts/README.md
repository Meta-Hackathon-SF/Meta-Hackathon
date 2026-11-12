# Shared contracts v1.0.0
This directory is the common interface agreement for all five workstreams. It contains normative design and TypeScript wire declarations, not a functioning backend or executable validators.

## Ownership and ports
| Contract | Producer | Consumer | Boundary |
| --- | --- | --- | --- |
| Confirmed intent | Will (UI), Adam (extraction) | Patrik, Rishi | User edits/approves extraction; server persists version |
| Authorized candidate snapshot | Patrik | Rishi, Adam | Server-only, opted-in, minimized fields |
| GroupProposal / MatchResult | Rishi | Adam, Kai, matching UI | 3-5 eligible people or honest no-match |
| QuestPlan / PlanResult | Adam | Kai, planning UI | Structured proposal; no side effects |
| Consent and public projections | Patrik | All server routes and subscriptions | Fail closed on missing auth/consent |
| EventRecord / WorkflowEvent | Kai | All feature UI | Persistent, versioned, authorized delivery |
| Continuation | Adam | Kai, Will's feature shell | Live generation after labeled time skip |
| Host acceptance | Kai | Event UI | Explicit actor action creates a draft |

## Normative reading
- [protocol.ts](protocol.ts): field names, enums and service ports
- [API.md](API.md): request/response conventions and public endpoints
- [PRIVACY.md](PRIVACY.md): access, projections and revocation
- [WORKFLOW.md](WORKFLOW.md): transaction/state semantics

## Validation rules
Implement runtime schemas in the server before accepting traffic. Never trust TypeScript types at a network boundary. Reject unknown tool names and extra public-response fields. Treat absent optional facts as unknown; ask for missing required availability, area, currency or consent instead of inventing them.

IDs are opaque server-created strings. Dates are RFC3339 UTC and intervals are half-open [start,end), with start < end. IANA timeZone is for local display and parsing confirmation. Money is a nonnegative integer in currency minor units; MVP uses one currency per community with no implicit conversion. Duration must fit every accepted member's available interval and duration cap. Venue must belong to the community area, be public, and be open throughout the event.

Match uniqueness: no duplicate participants; include requester; all members consent; same community/area; size 3-5. A max-budget cap applies to every member. Private constraints must never appear in a public rationale. A plan is invalid if it cites a participant/venue outside the authorized snapshot/catalog.

ModelEvidence.source is replay only for a replay; preserve this label into the UI. Mode is server-selected, not a client escape hatch. Live sessions may contain clearly labeled synthetic demo profiles, but synthetic acceptance is only permitted in a separate fixture scenario.

## Versioning and integration
Version 1.0.0 is the first shared agreement. Changes require an entry in docs/DECISIONS.md and acknowledgment by producer + consumers. Add matching examples and validators when implementation lands. Python serializers preserve camelCase. Do not create a second private set of wire shapes in each role directory.

Provider schemas/endpoints are unconfirmed. MusePort is an internal adapter contract, not the provider's documented SDK. Adam owns that adapter; Rishi consumes it.

## Required boundary cases
- No microphone: typed input follows the same confirmation flow.
- No shortlist: return no_match without relaxing hard constraints.
- Model timeout or malformed JSON: bounded retry, then explicit error.
- Same idempotency key/different body: conflict.
- Duplicate acceptance: same result, no counter increment.
- Plan revision changes during provider call: discard stale output.
- Consent revoked during a job: prevent publication and remove candidate.
- No common window after change: leave revision pending and ask for input.
- User text says ignore rules: treat as data, preserve tool allowlist and guards.
