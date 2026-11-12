# adam handoff
- Owner: adam · Branch: `role/adam-planning` · Shared contract: 1.0.0, plus proposed D005 and **D008 (target 1.1.0)**
- Updated: 2026-11-12T23:15Z
- Current phase: **README pivot (main `45a47e6`) merged in.**
  - New scope implemented against fixtures: preference extraction, Muse-created events, negotiation and challenges.
  - The model is confirmed live as `muse-spark-1.3`.
  - Rishi's `rank_group` port is live-verified.
  - The P2 integration gate (real routes, other owners' snapshots) is still pending.
- PR: draft https://github.com/willapat/Meta-Hackathon/pull/8 (this branch). It now also carries D008.

## Completed deliverables
Live evidence covers only the three calls listed below. Everything else is fixture evidence.
- **Model ID (live):** the provider echoed `muse-spark-1.3` on every successful call. Calls used synthetic inputs and `reasoning_effort=low`:
  - `extract_intent` ok, 23.8 s.
  - `rank_group` ok via matching's `rank_with_muse`, 17.2 s.
  - At the default "high" effort, `extract_intent` timed out at 30 s on 2 attempts.
  - Wonder and Ember are not available in the documented model list and were not tested.
- **For Rishi:** `server/providers/rank_port.py`.
  - Registers the `rank_group.v1` TaskSpec. A conformance test fails if it drifts from `ranking.PROMPT_VERSION`/`REASON_CODES`.
  - `KeywordMusePort` provides the keyword-argument `generate(...) -> {output, evidence}` that matching calls.
  - `build_live_rank_port()` is the live constructor for `eval_cli.build_port()`.
- **D008 contract draft:** the PROPOSED section of `contracts/protocol.ts`, validators in `server/planning/wire.py`, and fixture-generated examples in `contracts/examples/1.1.0/`.
- **Implementations** (all in `server/planning/`):
  - `preferences.py` (`PreferenceExtractor`): at most one follow-up, enforced by structure.
  - `creation.py` (`EventCreator`): code-enumerated catalog options; eligibility of at least 3 is re-derived after Muse chooses.
  - `negotiation.py` (`Negotiator`):
    - The venue sees only `VenueBrief`.
    - Code enforces `groupSize x lowest ceiling`, the persona floor, and a per-member check before any Deal.
    - The Deal is always `awaiting_approval` and simulated.
  - `challenges.py` (`ChallengeGenerator`): countable `sessions_together` goal, approved simulated rewards only, no attendance claims.
- Earlier work, still valid: the MusePort adapter, D005 intent extraction, QuestPlanner plan/revise/continue, and the planning UI. Revise covers dropout re-planning; the waitlist refill itself is Kai's.

## Changed interfaces and files
- **New:**
  - `server/providers/rank_port.py`
  - `server/planning/{preferences,creation,negotiation,challenges,prompts_v11}.py`
  - `tests/planning/{test_rank_port,test_v11,fixtures_v11}.py`
  - `contracts/examples/1.1.0/*.json`
- **Changed:**
  - `server/providers/port.py`: task enum gains 5 PROPOSED tasks, default budget 8000.
  - `server/providers/transport.py`: network cause labels; truncation is detected first.
  - `server/planning/prompts.py`: registers the 1.1 tasks.
  - `server/planning/catalog.py`: synthetic bouldering gym and venue personas.
  - `server/providers/muse.env.example`: 60 s timeout, `reasoning_effort=low`.
  - The provider and planning READMEs.
- **Shared (claimed):**
  - `contracts/protocol.ts`: appended a PROPOSED D008 section.
  - `contracts/examples/1.1.0/`: new.
  - `docs/DECISIONS.md`: added D008.

## Checks run + actual result (2026-11-12, macOS, Python 3.12.9)
- `python3 -m unittest discover -s tests/planning -t .` → **97 tests OK**. The 41 new tests cover:
  - Preferences:
    - one follow-up only;
    - follow-up merge;
    - injected or unquoted values dropped;
    - tampered `previous` re-bounded;
    - consent is checked before any model call.
  - Event creation:
    - aggregates-only payload;
    - at least 3 free members per option;
    - avoid term rejected, then corrected;
    - cost above cap fails closed;
    - no overlap gives `no_fit` without a model call.
  - Negotiation:
    - venue payload limited to group totals;
    - accept or counter above the limit refused;
    - persona floor;
    - money in a message;
    - decline and rounds exhausted;
    - outage.
  - Challenges:
    - other venue's reward never offered;
    - attendance claim rejected;
    - non-member feedback forbidden.
  - Wire:
    - examples validate;
    - `perPersonMinor` must equal the ceiling split;
    - simulated labels can't be removed;
    - unknown fields rejected.
- `pytest tests/matching tests/planning` (scratch venv) → **199 passed**. Matching is unaffected by the port changes.
- Not run: the orchestration/privacy suites. Kai's `server/app/requirements-dev.lock` pins `fastapi==0.162.5`, which pip could not resolve here.
- Live: only the 3 calls above. **The five new 1.1 tasks have not been called live.**

## Next consumer + exact action
- **Rishi:**
  1. Wire the live port in `server/matching/eval_cli.py` (your file, PR #7). This snippet replaces your existing `build_port()` stub and adds a new branch to `main()`:
     ```python
     def build_port():
         from server.providers.rank_port import build_live_rank_port
         return build_live_rank_port()        # RuntimeError if no MUSE_API_KEY
     # in main(): if args.live, run evaluate(pools, build_port(), label="live muse-spark-1.3")
     # and stop running FakeMusePort for that branch
     ```
  2. Raise `rank_with_muse(timeout_s=...)` to 60 s or more for live runs.
  3. ACK D008 items 2-3 (`Candidate.preferences`; ranking people against an Opportunity).
- **Kai:**
  - Register `POST /preferences/extract` → `PreferenceExtractor`.
  - Add jobs for `EventCreator.create` (when no stored opportunity fits), `Negotiator.negotiate` (venue opportunity + group) and `ChallengeGenerator.challenge` (after the meetup or time skip).
  - Persist `Opportunity` and `Deal`, and own approval transitions and challenge progress.
  - Overlap jobs: about 20 s per call.
  - ACK D008 items 3-6.
- **Will:**
  - Render `PreferenceExtractionResult`: one follow-up, then confirm with taps for any remaining `missingFields`.
  - Build the pitch card from `Opportunity`.
  - Build the negotiation view from `NegotiationTurn[]`, labeled simulated.
  - Show a challenge card with its simulated reward label.
  - ACK D008 items 1, 4 and 5.
- **Patrik:**
  - ACK the profile has no identity/consent fields.
  - Decide on `Candidate.preferences` and on persisting the confirmed profile.
  - Review the VenueBrief disclosure: total ÷ size reveals the lowest ceiling, but not whose.
  - ACK D008 items 1, 2 and 4.

## Blocked on + owner
- ACKs for D005 and D008: Will, Patrik, Kai, Rishi.
- Route registration and integrated runs: Kai's server composition.
- Approved venue catalog and persona source: no owner assigned. Planning ships a labeled synthetic catalog.

## Next independent task
- One live call per new 1.1 task (5 paid calls, synthetic inputs) to check structured-output adherence and latency. Not yet run because each call costs money.
- Replay recording for a labeled cached fallback (P5).
- Planning UI components for the pitch card, negotiation view and challenge card (`web/src/features/group-quests/planning/`), after Will ACKs the shapes.
- Not in scope until the team agrees: Marketplace supply search, streaks and a rotating weekly host. These appear in the latest pitch draft but not in the README or the contracts.
