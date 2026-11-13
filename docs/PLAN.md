# Delivery plan: Constellations weekly game (contract 2.0.0)
Deadline used in planning: Nov 13, 2026, 10:30 AM PST (team-supplied, not independently verified). Feature freeze 04:30 AM. 04:30-10:30 is UI, demo and submission only.

Per-person tasks, owned paths, interfaces and acceptance checks: [docs/roles](roles). Each owner develops independently against `contracts/protocol.ts` and `contracts/fixtures/`, then integrates through the ports.

## Eight-step build order
| Step | Exit criteria | Owners |
| --- | --- | --- |
| 1. Audit + approval | Repo audited, weekly-game spec approved, contract 2.0.0 and fixtures on main | done (Rishi) |
| 2. Foundation | Archived FastAPI app, Muse adapter, privacy/session code, voice boundary restored into owned paths, renamed, retested; Kai's registry lets every owner mount a router; D006 ACKed by all | Kai, Adam, Patrik, Will |
| 3. Daily loop | Join + consent, daily question, answer (voice/text), follow-up, catch-up, streaks, guess, Saturday lock, all on real phones | Will, Patrik, Adam |
| 4. Formation | Lock runs semantic formation, validation, names; baseline example ready; 30-player timing measured | Rishi, Kai |
| 5. Sunday reveal + chat | Reveal card, anonymous room, moderation, report/block, expiry, mutual reveal, SSE | Kai, Patrik |
| 6. Event nudges (first cut) | Mid-week nudge from venue allowlist posted into room | Adam, Kai |
| 7. Question generation + synthetic signals (second cut) | Generated questions behind operator approval; labeled synthetic aggregate signals in Sky | Adam, Rishi |
| 8. Sky + demo polish | Thresholded Sky on projector and phones, operator console complete, rehearsed demo, backup video | Kai (Sky UI), Rishi (numbers), Will (operator), all |

Steps 6 and 7 are the first scope cuts. Never cut: consent, safety screening, OutputGuard, Sky threshold, chat moderation, truth labels.

## Integration rhythm
Merge small PRs to main every 2-3 hours. After each merge, every owner merges `origin/main` into their clean role branch. A fixture-passing module is not a working journey; record live vs fixture evidence in handoffs.

## Top technical risk
`muse-spark-1.3` single calls observed at 17-24 s (2 calls, not a benchmark). Formation at lock must finish under 60 s for 30 players: M1 at submit time, M3/M4 once, M5 in parallel. Rishi measures, Kai orchestrates.

## Submission
Pitch opens with the problem (everyone thinks they are alone; Facebook shows everyone's best night). Cite research only with named sources. No impact claim without measurement. Backup video before 04:30. Do not claim deployment or submission until verified.
