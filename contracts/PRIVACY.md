# Privacy and access contract (Constellations)
Owner: Patrik. All owners enforce this at their boundaries. No player ever sees another player's words; only riddles, society identities and aggregate patterns. Enforced in server code, not by the model.

| Data | Self | Society members | Authorized server | Model provider |
| --- | --- | --- | --- | --- |
| Answer text (voice transcript included) | Own, edit/delete before lock | Never | Yes | Answer text + random per-call ID only |
| Guess | Own | Never | Aggregation only | Never (only aggregate counts) |
| Safety flag | Never shown as a flag; support card only | Never | Yes | M1 output only |
| Findable details | Own | Via riddles only | Yes | Needed items only (M6) |
| Consent, session, blocks | Own | Never | Auth/privacy only | Never |
| Society card and passphrase half | Own society | Society only | Yes | M5 output |
| Riddles | Seeker only, released levels | Never target's own | Yes | M6 output, must never quote |
| Display name after confirmed find | Yes | Confirmed finds only | Yes | Never |
| Sky aggregate | Everyone | Everyone | Yes | Counts only (M8), threshold applied |
| Venue / quest | Society | Society | Public places only | M7 input list |
| Operator trace | Sanitized | Never | Sanitized metadata | No secrets |

## Rules
- Auth from the server session; client cannot choose live/demo mode or act as another player. Browser never gets service credentials; if Supabase is directly reachable, enforce row policies and test with non-service credentials.
- Answers readable by author and server only; another session gets 403 on any answer endpoint. Guesses are stored separately from answers.
- Prompts contain only random player IDs and answer text. Prompt builder strips profile fields. Unit test on every prompt payload.
- Riddles, names, themes and headlines never contain 5+ consecutive words from any answer. No sensitive categories (health, sexuality, religion, finances, family trauma, home location). Model self-check is advisory; code filters decide.
- Sky shows a theme only at or above threshold (3 demo, 25 production). No line or stat identifies an answer.
- Hunt and quests only in public places; riddles use only self-approved findable details.
- Consent is three toggles (matchAnswers, writeClues, isAdult 18+). Missing or revoked consent excludes the player from jobs; revocation invalidates in-flight jobs and checks again at publish.
- Retention: delete anytime before lock; answers expire 14 days after the round (TTL job). Deleted answers are absent from any re-run. No zero-retention provider promise.
- Distress/harm: flagged answers are excluded everywhere; the player sees only the private support card with campus counseling and the 988 Suicide and Crisis Lifeline (US). The game never counsels.
- Blocks: blocked players are never placed in one society.
- Raw answers are never in shared tables, telemetry or logs. Label synthetic players ("Synthetic player").

## Required tests
Another player's session gets 403 on any answer endpoint; unit test on every prompt payload (random IDs and text only); fuzz test of no-quote checker with known answers; red-team list of 30 answers for sensitive terms; theme with 2 members never renders; seeded distress answer never appears anywhere; deleted answer absent from re-run; TTL expiry after 14 days; vetoed riddle never sent (P1); quest outside venue allowlist rejected; society with blocked pair rejected and re-solved; forged playerId; client-set mode escalation; service credential leakage; wrong found code reveals nothing. Disable a flow rather than bypass authorization to make the demo work.
