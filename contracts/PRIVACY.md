# Privacy and access contract
Owner: Patrik. All owners enforce this at their boundaries.

| Data | Self | Other members | Authorized server | Model provider |
| --- | --- | --- | --- | --- |
| Audio/transcript | During capture/confirmation | Never | Bounded transcription/extraction only | Only configured processing with opt-in |
| Intent/availability/budget | Own | Never directly | Required matching/planning services | Minimum approved structured fields |
| Public interests/display name | Own | Consented community/team scope | Yes | Prefer opaque IDs and interests |
| Consent/session credentials | Own consent only | Never | Auth/privacy only | Never |
| Proposal/event card | Eligible member | Same authorized group | Yes | Plan data needed for reasoning |
| Group messages | Member | Current members | Authorized conversation service | Not analyzed for MVP |
| Operational trace | Sanitized own status | Public progress only | Sanitized metadata | No secrets |

## Rules
Community opt-in is not blanket disclosure or indefinite authorization. Version matching and model-processing consents separately through the Consent revision. If matching or processing consent is absent/revoked, block model jobs and matching. Do not expose private constraints by explaining "Alex cannot afford more than $5"; use an allowlisted group-level statement such as "a free activity fits the group."

Public rationale must be validated or built from approved facts. A model instruction to keep secrets is insufficient. Profile IDs may be sent only as opaque identifiers. Raw transcripts are not stored in shared tables or telemetry. Specify short retention/deletion behavior in implementation; do not invent a zero-retention provider promise.

## Revocation
Leave removes room/subscription authorization immediately and invalidates in-flight plans. Recheck at write and publish time. History may retain minimized event metadata; do not continue exposing departed users' private fields. Cancel or revise events whose participation no longer qualifies.

## Database responsibilities
Patrik owns policies, access queries, consent logic and public projections. Kai owns workflow tables/transactions and ordering of migrations. They coordinate FK/table interfaces before implementation. Browser clients never get database service credentials. If using direct Supabase access, enforce row-level policies and test them using non-service credentials; API filtering alone does not secure a directly reachable table.

## Required tests
Cross-user intent GET/update; forged participantId; cross-room message read; revoked subscription reconnect; stale job publication after revoke; private data in model rationale; service credential leakage; fixture actor impersonation; client-set live/demo mode escalation. Disable a flow rather than bypassing authorization to make the demo work.
