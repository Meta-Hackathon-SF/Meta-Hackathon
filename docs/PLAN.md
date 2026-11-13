# 18.5-hour delivery plan: Constellations
For executable per-person instructions, use the [agent execution map](phases/README.md): [Rishi](phases/rishi.md), [Adam](phases/adam.md), [Will](phases/will.md), [Patrik](phases/patrik.md), [Kai](phases/kai.md). The shared phase gates apply to the complete integrated system; each checklist specifies that person's contribution.

Product: Constellations (D001), a campus constellation game inside Facebook Groups. Muse is Muse. Weekly Confession, Formation into constellations of 3-5 by meaning, Search with 3-level clues, in-person confirm, Sky reveal, Meetup plan (P1). Source of truth: the Constellations PRD (Nov 12, 2026).

Re-based anchor: work resumes Nov 12, 2026 16:00 PST; deadline Nov 13, 2026 10:30 AM PST (team-supplied, not independently verified; confirm with organizers). About 18.5 h remain. Feature freeze at 04:30 AM; 04:30-10:30 is UI, demo and submission only. If late, compress scope rather than moving the deadline.

| Phase | PST | Required exit |
| --- | --- | --- |
| P0 | Thu 16:00-17:00 | D001 and D003 ACK by all five (first item); contracts/protocol.ts 1.0.0 agreed; D002 server baseline confirmed; Muse call re-verified; branches and ownership confirmed |
| P1 | 17:00-20:00 | Each owner demonstrates their new module with labeled synthetic fixtures; Adam's adapter fake and Patrik's guard published |
| P2 | 20:00-23:00 | Integrated round on 3+ phones: join, confess, form, clues, confirm |
| P3 | 23:00-Fri 02:00 | Sky (guessed vs actual), safety triage, blocks, operator console complete; 30-player formation timed against 60 s |
| P4 | 02:00-03:30 | Meetup plan, clue veto (P1) only if P3 is green; hardening |
| P5 | 03:30-04:30 | Failure cases pass; FEATURE FREEZE 04:30; working backup captured |
| P6 | 04:30-10:30 | UI polish (mobile, keyboard, error states), 5-minute rehearsal, 2-3 minute backup recording, Devpost and submission links verified, final critical fixes only |

Suggested P6 split: 04:30-07:00 polish, 07:00-08:30 rehearsal plus backup recording, 08:30-09:30 submission and link verification, 09:30-10:30 critical fixes, final verification and rest. Functional UI exists by P2; schedule staggered rest, not five people simultaneously unavailable.

## Demo success criteria (must all be true at 10:30)
6+ real people answer on their own phones; constellations of 3-5 with name and shape in under 60 s; clues never quote an answer; two players confirm a match in person and see the line between their stars light up; Sky shows guessed vs actual prevalence; Muse model name and response metadata visible; every synthetic element labeled. Judging slot: 5 minute demo plus 3 minutes Q&A.

## Top technical risk
Observed `muse-spark-1.3` single-call latency was 17-24 s at low reasoning effort (2 calls, not a benchmark). Formation under 60 s for 30 players needs parallel calls (M5 per constellation, M6 per target/seeker, precompute while the round is open). Kai and Adam own this; record actual timings.

## Ownership at checkpoints
Rishi: formation validator and baseline -> live M3/M4 -> blocks, edge cases, baseline demo example.
Adam: adapter and Muse prompts -> M5/M6/M2 live in parallel -> M8, red-team, M7 (P1).
Will: shell migration, join, Confession -> live phones, QR, guess -> edit/delete, fallbacks, composition polish.
Patrik: consent, private answers, guard -> M1 triage, snapshots -> threshold, TTL, red-team, privacy table rerun.
Kai: round machine, operator, SSE, finds -> lock pipeline fan-out -> Sky, console, reset, meetup (P1), failure recovery.

Every person owns meaningful engineering work. Pitch/video/submission are shared wrap-up responsibilities. Only the shell (`web/`) exists on main; every server module is new. Before each session, check PRs and issues for tags (docs/COORDINATION.md section 1). When blocked on another owner, stop at the phase boundary, push, open a `[BLOCKED]` draft PR with the exact block and continue with a labeled test-only adapter (section 2).

## Cut order
Cut in this order: P2 vision items, Meetup, clue veto, voice (text always works). Never cut: consent, safety triage, the no-quote guard, the Sky threshold, truth labels ("Simulated Facebook", "Synthetic player", "Demo timing", "Replay of a saved round"). Never fake a live Muse response to meet a checkpoint.

## Submission preparation
Start Devpost text now (16:00); pitch opens with the problem (everyone thinks they are the only one; Facebook shows everyone's best night) and closes "Constellations shows you who's been shining next to you the whole time." Cite PRD figures with their sources only; make no impact claim (loneliness, retention, friendships) without measurement. Capture a working backup before 04:30; finalize links by 09:30. Confirm team, rules, public repository and video requirements against organizers' source. Do not claim deployment or submission is complete until actually verified.
