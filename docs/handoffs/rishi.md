# rishi handoff
- Owner: rishi
- Branch: role/rishi-matching
- Updated: 2026-11-12T21:15Z
- Current phase: P1 (independent module with synthetic fixtures)
- Status: verified offline with fixture MusePort; NOT live-integrated (no Muse adapter, privacy snapshots or server routes exist on any branch yet)
- Shared contract: 1.0.0, acknowledged without change (docs/DECISIONS.md D005)

## Completed deliverables
- `server/matching/models.py`: runtime validators for the matching slice of protocol.ts (Window, Context, ModelEvidence, PrivateIntent, PublicParticipant, Candidate, MatchInput, MemberVersion, GroupProposal, Matched/NoMatch). Reject unknown keys, non-UTC times, start>=end, duplicate members, size outside 3-5, contract version mismatch.
- `server/matching/feasibility.py`: hard gates (same community, same area, same currency as requester; >=30 min common window; maxDuration >= 30), pool cap 12, enumerate requester + 2-4 others, keep groups with a common window for every member, deterministic shared-public-interest baseline score, shortlist 8, no_match diagnosis (too_few / no_common_time / constraints).
- `server/matching/ranking.py`: `rank_with_muse` calls MusePort task `rank_group`, promptVersion `rank_group.v1`. Payload uses opaque refs (m0..), public interests, size, commonMinutes only. Output strictly validated: `{optionId:"g<i>", sharedInterests:[subset], reasonCodes:[1-3 from allowlist]}`. 20 s timeout, 2 attempts, then PROVIDER_UNAVAILABLE (retryable). Public rationale built from template + sanitized interest words only.
- `server/matching/service.py`: `MatchingService(muse).match(MatchInput|dict) -> Matched|NoMatch`; `recompute(prior, input)` (same proposalId, revision+1, removed members never appear); `is_stale(proposal, candidates)`; `public_projection(result, profiles)` (no memberVersions/feasibleWindows/private fields; keeps isSynthetic). Live mode rejects replay-labeled evidence.

## Checks run + actual result
`uv run --no-project --with pytest python -m pytest tests/matching -q` -> 102 passed (fixtures 28, feasibility 23, ranking 29, service 22).
Covered: touching windows, each gate, duplicates, requester missing (FORBIDDEN), sizes, privacy scan of Muse payload and public projection, prompt-injection text in interests, malformed/unknown model output, timeout + retry, provider down, live-vs-replay evidence, recompute/staleness.

## Fixture versus live evidence
All evidence is fixture: FakeMusePort (source "replay", model "fake-muse"), synthetic profiles. No real Muse call, latency or relevance numbers exist yet.

## Next consumer + exact action
- Adam: provide a MusePort implementation that supports task `rank_group` returning `{output, evidence}`; output schema above. Ack payload shape (opaque refs, no private fields).
- Patrik: provide authorized Candidate snapshot method for (communityId, requester session); confirm or replace `public_projection` with shared DTO validator. Matching assumes snapshot already excludes non-consenting members.
- Kai: register POST /api/v1/communities/:id/matches as a job calling `MatchingService.match`; persist GroupProposal; call `is_stale` before publish and `recompute` on availability/membership change.
- Will: matching card UI paused by direction; props will be the `public_projection` shape.

## Blocked on + owner
Live integration blocked on Adam (MusePort), Patrik (snapshots), Kai (server/app). Independent work continues.

## Next independent task
P2 prep: thin HTTP-agnostic job entrypoint for Kai, matching eval harness (baseline vs Muse on synthetic pools) for P5, then matching card UI when UI work resumes.
