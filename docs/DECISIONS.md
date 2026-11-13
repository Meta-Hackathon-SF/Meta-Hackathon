# Decisions

Format per entry: ID / UTC timestamp; decision and rationale; owner and affected producers/consumers; status; ACK evidence; contract version / migration; verification.
ACKs are recorded as a reply in the PR that proposed the decision (`ACK`, `CHANGE: ...`) and copied here with the PR link. See docs/COORDINATION.md.

## D001: Product and ownership
ID / UTC timestamp: D001 / 2026-11-13T00:00Z
Decision and rationale: Build **Constellations**, per the team PRD of Nov 12 2026. It is a campus constellation game inside Facebook Groups. Muse  reads private weekly confessions, forms constellations of 3-5 by meaning, writes clue chains, and reveals the community as a Sky of guessed vs actual prevalence. Main was reset to the mock Facebook web UI. Earlier Group Quests code is archived on `archive/group-quests-before-pivot` and is not part of this build.
Owners (branches unchanged):
- Rishi: formation engine (M3 theme discovery, M4 constellation formation, validation, keyword baseline), formation UI.
- Adam: single Muse adapter, Muse prompting, M2 clarify, M5 identity, M6 clues, M7 meetup plan, M8 Sky narration; Search UI.
- Will: join/QR, confession capture (voice/text), follow-up, guess slider, edit/delete, feature composition and routing; Muse metadata chip.
- Patrik: consent (3 toggles incl. 18+), private answers, blocks, M1 safety triage, output guard, Sky threshold, deletion and TTL; consent screen and support card.
- Kai: server scaffold, round lifecycle, parallel Muse job orchestration, find confirm, SSE, Sky aggregates, meetup event (P1), operator console, synthetic top-up, reset.
Status: proposed by Rishi.
ACK evidence: pending `@adamzhang06`, `@willapat`, `@patrikliska13`, `@beatopia`.
Contract version / migration: see D003.
Verification: documentation only; no runtime exists.

## D002: Server baseline
ID / UTC timestamp: D002 / 2026-11-13T00:00Z
Decision and rationale: Proposed server stack is Python FastAPI with PostgreSQL/Supabase, and the frontend stays the existing React/Vite shell. Kai scaffolds `server/app/` and owns dependency manifests and migration order. Patrik reviews auth and database access boundaries.
Status: proposed. Kai confirms or changes it at P0.
ACK evidence: pending `@beatopia`, `@patrikliska13`.
Verification: none yet.

## D003: Contract 1.0.0
ID / UTC timestamp: D003 / 2026-11-13T00:00Z
Decision and rationale: `contracts/protocol.ts` 1.0.0 defines the Constellations wire types, Muse job I/O M1-M8 and the ports between owners (MusePort, FormationPort, OutputGuard). JSON keys are camelCase everywhere. Each producer must ACK its shapes; any change goes through a PR plus an entry here.
Status: proposed.
ACK evidence: pending all owners.
Contract version / migration: 1.0.0, first version.
Verification: `tsc --noEmit --strict contracts/protocol.ts` at the commit that adds it.

## D004: Coordination protocol
ID / UTC timestamp: D004 / 2026-11-13T00:00Z
Decision and rationale: Every agent checks open PRs/issues for tags before work, and answers requests first. When an agent needs another owner's interface, data, ACK or endpoint, it stops at the phase boundary, pushes, opens a `[BLOCKED]` draft PR tagging the owner with the exact need, and continues only behind a labeled test-only adapter. See docs/COORDINATION.md.
Status: accepted (team direction from Rishi).
ACK evidence: n/a (process rule); each owner confirms by following it.
