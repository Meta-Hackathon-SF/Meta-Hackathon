# Demo and Q&A
Status: a rehearsal plan for a system that is not yet built. Only the Facebook shell exists on main. Every beat below is a target, not a result. Requests between owners follow [COORDINATION.md](COORDINATION.md).

Slot: 5 minute demo plus 3 minutes of Q&A. The room plays live on its own phones. Judging weights: AI Integration 30%, Product 25%, Execution 25%, Originality 20%. Deadline used in planning is Nov 13, 2026, 10:30 AM PST (team-supplied, not verified). Confirm event rules for the slot.

## Five minutes
Open with the problem, not the product. Everything below is a target for rehearsal, not a measured result.

| Time | Beat | On screen | Who |
| --- | --- | --- | --- |
| 0:00-0:30 | Problem. "Nearly half of first-year students believe everyone else has more friends." Facebook shows everyone's best night. Constellations shows everyone's real week. Cite Whillans et al. 2017 via WEF. | Slide, "Simulated Facebook" label | Presenter |
| 0:30-1:10 | QR join. Room scans, sees the explainer, accepts the three consent toggles (match me, write clues, 18+), picks a name and color. | QR on projector; phones | Will's flow; Patrik's consent |
| 1:10-1:50 | Confession. Operator shows the question. Room answers by voice or text, answers one Muse follow-up if asked, then moves the guess slider. | Operator console: answer count, safety screen counter | Operator (Kai) |
| 1:50-2:05 | Lock. Operator taps Lock Round. Show the baseline example: a keyword baseline splits "cooking for one is depressing" and "I eat in my room so no one sees me alone". Muse joins them. | Split view, Muse chip (model, call type, latency) | Rishi |
| 2:05-2:50 | Formation. Each phone shows constellation name, shape, found code and number of members to find. Say the real latency on screen. | Formation cards, per-call latency in console | Presenter |
| 2:50-3:30 | Search. Clue levels unlock on operator tap or every 20 seconds, labeled "Demo timing". Cryptic, then medium, then direct. Players look around the room. | Clue cards on phones | Adam's UI |
| 3:30-4:10 | Two people confirm on stage. Each reads the other's 4-character found code from their phone and enters it. Their link lights up. | Stage pair; constellation light-up | Two volunteers |
| 4:10-4:45 | Sky on projector. Constellations as constellations, confirmed finds as lines. Guessed vs actual prevalence per theme. Themes appear only at 3+ players. | Projector Sky view | Kai |
| 4:45-5:00 | Close. Muse proposes, code enforces. One-line vision (seasons, Grand Gathering) and the 30 second pitch's last line. | Slide | Presenter |

Cut order if behind: skip the baseline example, then skip the second follow-up, then shorten the Search to one level. Never cut consent, the model chip or labels.

## What to show about the AI
- The model chip on every Muse output: `muse-spark-1.3`, call type (M1 to M8), latency.
- Constellation reasoning: the shared meaning Muse returned for one constellation, never a member's words.
- One live validation: show the guard rejecting or passing a Muse output.
- Do not describe code checks (size, blocks, thresholds) as Muse reasoning.

## Demo modes and labels
| Item | Label |
| --- | --- |
| Facebook shell | "Simulated Facebook" |
| Seeded answers | "Synthetic player" |
| Accelerated clue unlocks | "Demo timing" |
| Cached response | "Replay of a saved round" |
| Real room answers | Live, persisted |

## Q&A prep (3 minutes)
**How is this better than keywords?** Show the baseline example. A keyword or embedding-cluster baseline splits two people who meant the same thing. Muse groups them. We have not measured an improvement and do not claim one.

**Privacy: can anyone see my answer?** Only you and the server. Other players see clues, constellation identities and aggregate themes. Prompts carry random player IDs and answer text only, with no names, emails, photos or tokens. Clues pass a no-quote check (no 5+ consecutive words from any answer) and a sensitive-term check. Themes below the threshold never render. You can delete before lock; answers expire 14 days after the round. The access rules are enforced in server code; see [contracts/PRIVACY.md](../contracts/PRIVACY.md).

**Safety: what if someone is in distress, or a stranger is dangerous?** Muse screens every answer first. Flagged answers are excluded from matching, clues and themes. That player sees a private card with campus counseling and the 988 Suicide and Crisis Lifeline (US). The game does not counsel. The search happens in shared public spaces, clues use only details the player marked as findable, blocks are respected, and quests use public venues. Friendship only, 18+.

**Why does this need AI?** No human can read thousands of private answers, match them by meaning, and write safe, personal clues for every player every week. No chatbot sees more than one person. Code cannot understand what a confession means. Code then validates every output.

**Latency, honestly.** In 2 earlier live calls (before the repo reset), single-call latency was 17 to 24 s at low reasoning effort. We use parallel calls (constellation identity per constellation, clues per pair) and say the measured formation time on screen. If it misses 60 seconds, say so. Wonder and Ember were not tested; organizer confirmation of the model is open.

**Why Facebook?** Groups already hold the community and trust. This prototype simulates the shell and claims no Groups, Messenger or Events API access.

**Retention or loneliness impact?** None claimed. We list metrics we would track (answer rate, Sky opens, constellations fully found in 5 days, first quest, meeting again within 3 weeks) with no targets.

Competitors: not needed in the demo or Q&A. Do not spend time on them.

## Fallback plan
| Failure | Response |
| --- | --- |
| Too few real players | Operator loads the synthetic top-up. Every seeded answer shows "Synthetic player". Say so aloud. Real players must still make up the confirm on stage. |
| Muse provider outage or timeout | Operator console shows a retryable error. Retry once. Otherwise play the recorded round, labeled "Replay of a saved round", with the original inputs only. |
| Formation slower than 60 s | Keep talking over the console latency numbers; do not hide them. |
| Microphone fails | Text answers work with no session loss. |
| Wi-Fi fails | Phone hotspot; then the labeled replay and backup video. |
| A flagged answer appears | Show the private card only to that player. Never display it on the projector. |

## Before presenting
- Check mic permission, device networking, reset isolation, provider key and links.
- Run the full round on 3 or more phones at least twice.
- Record a 2 to 3 minute backup video of the live flow with visible labels, subject to confirmed rules.
- Reset the room and confirm no earlier answers remain.
- Verify every claimed number on screen came from the server.

## Thirty-second pitch
Nearly half of first-year students believe everyone else already has more friends than they do. That belief keeps them from reaching out, and Facebook mostly shows them everyone's best night. Constellations shows everyone's real week. Each week Muse, privately asks one honest question, groups the five people whose answers mean the same thing into a constellation, and gives each of them clues about the others. When two people find each other they confirm in person with a found code. On Sunday the community appears as a night sky.
