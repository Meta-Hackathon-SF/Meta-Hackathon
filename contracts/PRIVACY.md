# Privacy and access contract (Constellations 2.0.0)
Owner: Patrik. Every owner enforces it at their boundary. No player ever sees another player's answers. Players see their constellation's name and anonymous handles, chat messages that passed moderation, aggregate Sky patterns, and real identities only after a mutual reveal. Enforced by server code, not by the model.

| Data | Self | Room members | Server | Model provider |
| --- | --- | --- | --- | --- |
| Daily answer (incl. transcript) | Own, edit/delete until lock | Never | Yes | Text + random per-call id only |
| Weight, streak, catch-up state | Own | Never | Yes | Never |
| Prevalence guess | Own | Never | Aggregation only | Never |
| Safety flag | Support card only | Never | Yes | M1 output |
| Consent, session, blocks, reports | Own | Never | Privacy/operator only | Never |
| Constellation name, shape, color | Own constellation | Yes | Yes | M5 output |
| Anonymous handle | Own | Yes | Yes (mapping private) | Never |
| Chat message | Own | Yes, if visible | Yes | Message text only for M1 |
| Real identity | Own | Only after mutual reveal, only that pair | Yes | Never |
| Sky aggregate | Everyone in community | Everyone | Yes | Counts only (M8) |
| Event nudge | Room | Room | Yes | Venue list + sharedMeaning (M7) |
| Operator trace | n/a | Never | Sanitized metadata | No secrets |

## Rules
- Identity from the server session. Browser never gets provider or service credentials.
- Answers readable by author and server only. Guesses stored apart from answers.
- Prompt builder strips everything except random ids and text. Unit test on every prompt payload.
- OutputGuard on every Muse public text and every chat message: no 5+ word quote of any answer, no sensitive category, no PII, no contact info before mutual reveal. Model self-checks are advisory; code decides.
- Sky threshold 3 demo / 25 production; suppressed themes reveal only a count.
- Consent toggles: matchAnswers, anonymousChat, isAdult (18+). All required to play. Revocation removes the player from future jobs and from the open room.
- Retention: delete anytime; answers, guesses and chat text expire 14 days after cycle lock. Deleted data absent from any re-run.
- Distress or harm (answers or chat): excluded from every output; the player sees a private card with campus counseling and the 988 Suicide and Crisis Lifeline (US). The game never counsels.
- Block: blocked pair never shares a constellation; blocker stops seeing the handle's messages.
- Report: hidden for reporter immediately; operator review; repeat reports auto-hide.
- Mutual reveal only when both asked; a one-sided request leaks nothing.
- Synthetic players and signals always labeled; never counted as real participants.
- No raw answers or chat text in logs or telemetry.

## Required tests
Another session gets 403 on any answer route; prompt payload unit tests; no-quote fuzz; 30-item sensitive red-team list; 2-member theme never renders; seeded distress answer and distress chat message never appear; deleted answer absent from re-run; TTL expiry; forged playerId; client-set demo mode; contact info in chat before reveal rejected; one-sided reveal leaks nothing; blocked pair rejected and re-solved; venue outside allowlist rejected.
