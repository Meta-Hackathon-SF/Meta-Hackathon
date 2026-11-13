# rishi update log
Append entries; never include real participant data or credentials.
Format: UTC timestamp | branch/commit | phase/status | interfaces/files | checks/results | tags sent/answered | blocker

2026-11-13T00:00Z | main | reset to Constellations foundation | docs only | none | none | none

2026-11-12 | main | weekly-game pivot (contract 2.0.0) | docs/roles/rishi.md rewritten | none | none | none
2026-11-13T00:30Z | role/rishi-matching | step 4 formation core, fixture-verified | server/matching/*, tests/matching/* | pytest 25 passed; ruff clean | ACK requests to Patrik, Adam, Kai in PR | none
2026-11-13T01:30Z | role/rishi-matching | contract alignment + Sky prevalence, fixture-verified | server/matching/sky.py, tests/matching/test_sky.py | pytest 43 passed; ruff clean | DELIVERED to Kai on #11; guess-source ask to Patrik | none
2026-11-13T02:20Z | role/rishi-matching | Muse task specs + live_eval harness, fixture-verified | server/matching/{muse_specs,live_eval}.py, tests/matching/test_live_eval.py | pytest 46 passed; ruff clean | none | live timing needs MUSE_API_KEY
2026-11-13T02:35Z | role/rishi-matching | formation debug view (operator only, ids only) | web/src/features/constellations/formation/* | npm run lint ok; npm run build ok | Will to mount in operator console | none
2026-11-13T03:20Z | role/rishi-matching | gold-set quality eval + partition stress | server/matching/evaluation.py, live_eval --gold, tests | pytest 50 passed; ruff clean; baseline precision 0.15 on gold | answered #13 #14, D008 | live needs MUSE_API_KEY; guard/snapshot from Patrik
2026-11-13T03:50Z | role/rishi-matching | M4 repair before re-solve | server/matching/repair.py, formation/prompts/models edits, tests/matching/test_repair.py | pytest 57 passed; ruff clean; fuzz 375/400 repaired, 0 invalid | none | live runs deferred
2026-11-13T04:10Z | role/rishi-matching | MatchingPort composition for Kai | server/matching/port.py, tests/matching/test_port.py | pytest 64 passed; ruff clean; passes Kai wire + validate_partition | none new | Patrik guard/snapshot/guesses pending
2026-11-13T04:45Z | role/rishi-matching | live latency fix after Adam run (130.5 s) | formation/sky/port + tests/matching/test_schedule.py | pytest 66 passed; ruff clean; simulated replay 59.4 s | asks Kai wait_for 60 -> 120; Adam rerun | live rerun pending
2026-11-13T05:30Z | role/rishi-matching | debug getter, real OutputGuard, Sky overlap in harness | port.py, formation.py, models.py, live_eval.py, tests | pytest 69 passed; ruff clean | answers Kai #13/#26 debug ask; asks Patrik bulk guesses | #31/#33 need team-lead decision

2026-11-13 UI checkpoint: isolated role/rishi-matching checkout based on f7f182d. Daylight cards, readable main composer including retained draft while saving, full-width name input, straight week strip with question tooltips, unified Space mark and desktop navigation deduplication. Build passes; lint has two pre-existing warnings. Browser/server sandbox blocked visual and journey checks. No backend or Sky renderer change. Remote access unavailable; prepared local commit for review, not deployed.
