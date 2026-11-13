# Shared contracts: Constellations 1.0.0 (proposed, pending D003 ACK)
Common interface agreement for all five workstreams. Normative design and TypeScript wire declarations, not a running backend or executable validators.

## Versioning
- [protocol.ts](protocol.ts): the Constellations contract, `CONTRACT_VERSION = "1.0.0"`. It is the first Constellations contract and is pending ACK under D003 in docs/DECISIONS.md from all five owners.
- Earlier Group Quests contracts are gone from main; they survive only on branch `archive/group-quests-before-pivot` as reference. Do not import from there.
- Changes after ACK need a DECISIONS.md entry and producer + consumer acknowledgment, following the stop-and-tag flow in [docs/COORDINATION.md](../docs/COORDINATION.md). Python serializers preserve camelCase; no private wire shapes per role directory.

## Normative reading
[protocol.ts](protocol.ts) types and ports; [API.md](API.md) routes; [PRIVACY.md](PRIVACY.md) access and tests; [WORKFLOW.md](WORKFLOW.md) state and job pipeline.

## Ownership (proposed, D001)
| Contract | Producer | Consumer | Boundary |
| --- | --- | --- | --- |
| Join, ConsentV2, Answer, Guess, FindableDetails | Will (UI), Patrik (storage) | Kai, Adam, Rishi | Answer 1-400 chars, voice or text, edit/delete before lock |
| M2 clarify, M5 identity, M6 clues, M7 quest, M8 narration, MusePort | Adam | Kai, Rishi, UI | One Muse adapter; strict JSON; output guarded |
| M1 safety screen, OutputGuard, blocks, Sky threshold, TTL/delete | Patrik | All | Fail closed |
| M3 themes, M4 constellations, FormationPort | Rishi | Kai, Adam | Validated constellations only |
| Round lifecycle, jobs, finds, SSE, Sky aggregates, meetup, operator | Kai | All UI | Persistent, idempotent, authorized |
| Muse chip component, Search/Formation/Sky views | Will, Adam, Rishi, Kai per screen | Players | Chip shows model, call type, latency |

## Validation rules
Implement runtime schemas on the server before accepting traffic. Never trust TS types at a network boundary; reject unknown fields in public responses and unknown task names.
- Constellations: size 3-5; every consenting, unflagged player placed exactly once; no blocked pair; weak matches get `isLooseMatch` and the honest label, never dropped.
- No-quote: no clue, constellation name, theme label or headline contains 5+ consecutive words from any answer.
- Sensitive categories (never in clues or labels): health, sexuality, religion, finances, family trauma, location of home. Sensitive-term filter plus M6 self-check field.
- Sky: a theme renders only if count >= threshold (3 demo, 25 production).
- Prompts contain only random per-call player IDs and answer text. No names, emails, photos, session tokens, profile fields.
- M8 receives counts only; every number in its headlines must equal server counts exactly.
- Every Muse call: strict JSON, schema-validated, one retry on invalid JSON, then a labeled fallback or retryable operator error. Muse proposes, code enforces.
- Found code: 4 characters; find is mutual, idempotent, unique per pair.
- Meetup venues come from the approved public list and fit the budget cap; nothing created below 3 "In".
- ModelEvidence.source is replay only for a saved round; UI shows "Replay of a saved round". Other labels: "Simulated Facebook", "Synthetic player", "Demo timing".
- Auth from the server session only; never accept playerId as identity. Mode (live/demo timing) is server/operator-set, never client-escalated. Browser never receives service credentials.
- IDs opaque and server-created; dates RFC3339 UTC.

## Required boundary cases
- Voice fails: typed input follows the same flow.
- Vague answer: at most one follow-up per player per round.
- Flagged (distress/harm) answer never appears in any prompt after M1, clue, constellation, theme, Sky or log.
- Wrong found code reveals nothing (generic "not a match", no constellation membership leak).
- Duplicate confirm is idempotent; same key with different body returns 409.
- Provider outage: retryable operator error, or a cached result labeled replay.
- Deleted answer is absent from a re-run.
- Constellation with a blocked pair is rejected and re-solved.
- Prompt injection inside answers ("ignore rules") stays data; guards and allowlists unchanged.
- Consent revoked mid-job: nothing published for that player.
- Formation for 30 players under 60 s (see WORKFLOW latency note).
