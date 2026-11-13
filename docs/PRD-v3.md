# Facebook Space v3: backend spec by screen

Status: **proposed (D012, contract 3.0.0)**. Needs ACK from all five owners before implementation. Supersedes Sky statistics, the prevalence guess and constellation naming of 2.x.

Base path `/api/v1`, session cookie, `Idempotency-Key` on mutations, errors `{error:{code,message,requestId,retryable}}`. Existing routes are in `contracts/API.md`, wire types in `contracts/protocol.ts` (2.1.0). This document is backend only. UI owners keep their own screen notes.

## 1. What changed

v2 made the player wait a week for one reveal and then showed percentages. v3 gives a reveal every day. After answering Monday to Friday, the player immediately sees the constellations they belong to that day, in that day's color, and the only number shown is how many people answered today. Saturday shows the whole week and the whole sky (about 10,000 people, no zoom), with each constellation-star's two biggest other constellations faintly. After a loading screen where the algorithm visibly tries connections, Sunday reveals one main constellation of the player's closest people (3-5 including the player), drawn as the Meta logo, and opens a 24-hour anonymous chat. Nothing has a name: not constellations, not the chat room. Events use constellation overlap as a private signal for nudges and for generated custom events.

Removed: prevalence guess (`PUT /cycles/:id/guess`, `GuessCard`), Sky statistics and percentages (`GET /cycles/:id/sky`, `SkyStats`, `SkyTheme`), constellation names and shapes (`Constellation.name`, `shapeId`), Muse tasks M5 (constellation naming) and M8 (Sky narration), `SyntheticSignal` on player-facing paths, chat room title.

Added: instant daily placement, daily constellation reveal, `answeredToday`, week view of day constellations, Saturday sky (stars + layout + second degree), formation progress stream, main constellation with Meta-logo anchors, event constellation-interest counts and nudge eligibility, custom events (cluster finder, proposal, approval, RSVP), `eventSignals` consent toggle.

## 2. Screen inventory

Status key: exists = on main and keeps its backend; changes = on main, backend changes; new = no UI or backend yet; removed = delete.

| # | Screen | Route / where | UI owner | Backend owner | Status |
| --- | --- | --- | --- | --- | --- |
| S0 | Home feed card (`daily/FeedCard.tsx`) | `/` in `HomePage` | Will | Will (cycle state), Kai (compose) | changes |
| S1 | Join and consent (`JoinScreen`, `PrivacyGate`) | `/space` gate | Patrik | Patrik | changes |
| S2 | Privacy and data settings, support card (`PrivacySettings`, `SupportCard`) | `/space` panel | Patrik | Patrik | changes |
| S3 | Today: question and answer, text and voice (`DailyPage`, `QuestionPost`, `useVoiceRecorder`) | `/space` | Will | Will, Patrik (M1) | changes |
| S4 | Follow-up question | `/space`, inline after answer | Will | Adam (M2) | exists |
| S5 | Daily constellation reveal | `/space`, right after answer | Kai | Rishi | new |
| S6 | Your week, Mon-Fri (`WeekGraph`) | `/space` | Will | Will, Rishi | changes |
| S7 | Catch-up | `/space` "Catch up" group | Will | Will | exists |
| S8 | Streak and rewards (`StreakRewards`) | `/space` | Will | Will | exists |
| S9 | Saturday sky | `/space` Saturday | Kai | Rishi, Kai | new |
| S10 | Forming / loading | `/space` Sat to Sun | Kai | Rishi, Kai | new |
| S11 | Sunday main constellation, Meta logo reveal | `/space` Sunday | Kai | Rishi | new (replaces `ConstellationPreview`, `MatchReasons`) |
| S12 | 24-hour anonymous chat, report, block, mutual reveal (`chat/ChatPanel`) | `/space` Sunday | Kai | Kai, Patrik | changes |
| S13 | Events list and event nudge (`EventsPage`, `nudges/NudgeCard`, `EventHeat`) | `/events`, feed, `/space` | Adam | Rishi (counts), Adam (catalog, copy) | changes |
| S14 | Custom event invite and RSVP | `/events`, notification | Adam | Rishi (cluster), Adam (proposal), Patrik (RSVP) | new |
| S15 | Operator console (`/space/operator`, `OperatorConsole`, `FormationDebug`, `OperatorNudgePanel`) | `/space/operator` | Will | Will, Kai, Rishi, Adam | changes |
| R1 | Prevalence guess card (`GuessCard`) | `/space` | n/a | n/a | removed |
| R2 | Sky statistics and percentages | `/space` Saturday | n/a | n/a | removed |
| R3 | Constellation names and shape labels | everywhere | n/a | n/a | removed |

## 3. Shared model

Week timeline (all times community-local, demo timing via operator):

| When | Player sees | Backend event |
| --- | --- | --- |
| Mon-Fri on answer | that day's constellations, `answeredToday` | instant placement |
| Mon-Fri end of day | nothing new | day close |
| Saturday 12:00 | cycle locks, loading screen | week lock, sky layout, main formation |
| Saturday to Sunday | forming screen | progress stream |
| Sunday 10:00 | main constellation, chat opens | reveal |
| Reveal + 24 h | chat closes | room expiry |

Wire identity rules:
- A star is an integer index into this week's sky, randomized per cycle. It is never a player id. `myStarIndex` identifies the viewer only to the viewer.
- Constellations have an opaque `constellationId` and a `colorId` (day), no name.
- Co-membership graph: for week W, edge weight between two players is the number of constellations they share. Stored server side only, ids never leave the server.

Instant placement (Rishi): on answer accept, embed the answer weight vector with the local baseline matcher (no Muse), assign the player to up to `MAX_DAILY_CONSTELLATIONS` (default 3) existing or new same-day clusters by similarity above threshold. Day close (Rishi, batch) re-forms the day with the final answer set; players keep membership of clusters that survive, others are replaced. The UI reads `daily.updated` to redraw.

Brightness: `bright | mid | faint` banded by code per viewer, raw score never sent (D009).

## 4. Screens

### S0. Home feed card

Purpose: entry point into Facebook Space from the feed.

Reads
- `GET /session` -> `{ player: PlayerSelf | null, consent: Consent | null, isOperator: boolean }`
- `GET /cycles/current` -> `CurrentCycleView` (see section 6), uses `cycle.phase`, `today.day`, `answeredToday`, `streak`.

Actions: none.

SSE: `cycle.phase` (phase change), `daily.updated`.

Jobs: none.

Muse: none.

Privacy: unauthenticated callers get `{ player: null }` and no cycle data; `answeredToday` is a count only, shown to joined players only.

Errors: `UNAUTHENTICATED` (render join prompt), `NOT_FOUND` (no open cycle).

Empty states: `cycle: null` when no cycle is open; `today: null` on Saturday and Sunday; `answeredToday: 0` is valid.

Backend owner: Will (cycle), Kai (composition).

### S1. Join and consent

Purpose: join a community, set consent toggles before any data is stored.

Reads
- `GET /session`.
- `GET /communities/:id` -> `{ id, memberCountBucket, consentCopyVersion }`.

Actions
- `POST /communities/:id/join` body `{ displayName, matchAnswers, anonymousChat: boolean, eventSignals: boolean, isAdult: boolean }` -> `{ player: PlayerSelf, consent: Consent }` + session cookie. `isAdult: false` -> 403 `FORBIDDEN`.
- `PATCH /me/consent` body `{ expectedVersion: number, toggles: Partial<ConsentToggles> }` -> `Consent`. Revocation invalidates queued jobs, leaves rooms, and drops event signals when `eventSignals` goes false.

`ConsentToggles` = `{ anonymousChat, useActivity, eventSignals, voiceInput }`. New in 3.0.0: `eventSignals` (default off).

SSE: none.

Jobs: none. Consent is rechecked by every job before it executes (D004).

Muse: none. Free-text `matchAnswers` run through M1 (safety_screen) at submit, not on the read path.

Privacy
- Consent rows are versioned; stale write -> 409 `STALE_REVISION`.
- Session is httpOnly, same-site; client-supplied player ids are ignored.
- `displayName` never appears on any other player's wire view.

Errors: `INVALID_INPUT`, `FORBIDDEN`, `CONSENT_REQUIRED`, `STALE_REVISION`, `RATE_LIMITED`.

Empty/edge: joining mid-week is allowed, earlier days count as catch-up; joining after Saturday lock returns `joinedFor: "next_cycle"`.

Backend owner: Patrik.

### S2. Privacy and data settings, support card

Purpose: let the player control data, delete it, and reach help.

Reads
- `GET /session` (consent state).
- `GET /me/activity` -> `{ useActivity: boolean, topics: string[] }` (allowlisted topics only).
- `GET /support` -> `{ resources: { id: Id; label: string; url: string }[] }` static, from an approved list.

Actions
- `PATCH /me/consent` (as S1).
- `PUT /me/activity` body `{ useActivity, profileId?, groupIds, eventIds, friendIds, texts }` -> `{ useActivity, topics }`. Off deletes stored signals. Texts reduce to allowlisted topics and are discarded.
- `PUT /me/event-signals` body `{ eventIds: Id[] }` -> `{ stored: number }`. Requires `eventSignals`. Interest and RSVP are private (S13).
- `POST /me/blocks` body `{ roomId, handle }` -> 204, no existence leak.
- `DELETE /me/data` -> 202. Deletes answers, follow-ups, activity signals, event interests and RSVPs, chat authorship links, co-membership edges for the player; stars are removed from the week's pending sets.

SSE: none.

Jobs: retention sweep (Patrik): answers, follow-ups, event interests, RSVPs/invites, daily placement and co-membership edges are deleted 14 days after the cycle's lock; chat message text 7 days after room expiry, whichever comes first (canonical, Patrik on #54; supersedes "30 days after week close"). Other owners purge their per-cycle data via `AnswerStore.expired_cycles()`.

Muse: none.

Privacy: deletion is idempotent and bound to the session; after 202 the next job run must not include the player. Support resources never contain player data.

Errors: `UNAUTHENTICATED`, `CONSENT_REQUIRED`, `STALE_REVISION`, `RATE_LIMITED`.

Edge: `DELETE /me/data` mid-week removes the player from today's constellations; other members' views update via `daily.updated` without a visible reason.

Backend owner: Patrik.

### S3. Today: question and answer (text and voice)

Purpose: show today's question and take the answer.

Reads
- `GET /cycles/current` -> `CurrentCycleView`.
- `GET /cycles/:id/questions` -> `DailyQuestion[]` released so far, never future days.
- `GET /cycles/:id/answers/:day` -> `DailyAnswer | null` (own answer only).

Actions
- `POST /cycles/:id/answers` body `{ day: 1|2|3|4|5, text: string /* 1-400 */, source: "text" | "voice" }` -> 202 `{ answer: DailyAnswer, placement: "pending" | "ready" }`. Server sets weight (on-day 1.0, catch-up lower). M1 safety screen runs at submit via Patrik. On accept, instant placement is enqueued.
- `PATCH /cycles/:id/answers/:day` body `{ text }` -> `DailyAnswer`; re-runs M1 and re-places. 409 `CYCLE_LOCKED` after Saturday 12:00.
- `DELETE /cycles/:id/answers/:day` -> 204; removes player from that day's constellations.
- `WS /voice/live` (PROPOSED): binary PCM16 mono 16 kHz frames, text `stop` -> `{type:"ready"}`, `{type:"partial"|"final", text}` (final up to 400 chars) or `{type:"error", code, message, retryable}`. Needs session cookie, `voiceInput` consent, same-host origin. Mounted only when live STT is configured. Produces a draft only; the player submits through `POST answers`. Raw audio is never stored or logged.

SSE: `daily.updated` (own placement ready), `cycle.phase`.

Jobs: instant placement (Rishi), day close (Kai runs, Rishi forms).

Muse: M1 safety_screen at submit (Patrik). Placement itself uses no Muse call.

Privacy
- Only the owner can read a `DailyAnswer`. No endpoint returns another player's text.
- `answeredToday` is a count of distinct players with an answer for the current day, computed by Will, no per-player data.
- Safety-flagged answers are excluded from placement and from every game output; the player sees a neutral rejection or support card, not the flag.

Errors: `INVALID_INPUT` (length), `CONSENT_REQUIRED`, `CYCLE_LOCKED`, `NOT_FOUND` (day not released), `RATE_LIMITED`, `PROVIDER_UNAVAILABLE` (M1 down: answer is held, `retryable: true`, never auto-accepted).

Edge: duplicate POST for same day with a new `Idempotency-Key` -> 409 `STALE_REVISION` (use PATCH). Answering a future day -> 404.

Backend owner: Will (answers), Patrik (M1, consent), Rishi (placement).

### S4. Follow-up question

Purpose: one optional clarifying question after a vague answer.

Reads
- `GET /cycles/:id/answers/:day/followup` -> `{ needsFollowup: boolean, question: string | null }` (M2, max one per answer, cached).

Actions
- `POST /cycles/:id/answers/:day/followup` body `{ text: string /* 1-400 */ }` -> 202 `DailyAnswer` with the follow-up merged into the weight. M1 at submit.

SSE: none.

Jobs: none.

Muse: M2 clarify (Adam). Off the instant-placement path: placement runs first, the follow-up only refines at day close. Timeout 3 s, then `needsFollowup: false`.

Privacy: the question is generated from the player's own answer only. OutputGuard checks it for quoted text of other players and sensitive terms (it never has other players' text as input).

Errors: `PROVIDER_UNAVAILABLE` (treated as no follow-up), `CYCLE_LOCKED`, `NOT_FOUND`.

Backend owner: Adam.

### S5. Daily constellation reveal (new)

Purpose: right after answering, show the player the constellations they are in today.

Reads
- `GET /cycles/:id/days/:day/constellations` ->

```ts
interface DailyConstellationsView {
  day: 1 | 2 | 3 | 4 | 5;
  colorId: DayColorId;
  answeredToday: number;
  placement: "pending" | "ready" | "final";   // final after day close
  myStarIndex: number;
  constellations: {
    constellationId: Id;
    starIndices: number[];                    // includes myStarIndex, 3-12 stars
    brightness: "bright" | "mid" | "faint";   // per viewer
    anchors: { index: number; x: number; y: number }[]; // layout positions in 0..1
  }[];                                        // 0..MAX_DAILY_CONSTELLATIONS
}
```

Actions: none.

SSE: `daily.updated` `{ day }` when placement becomes ready or day close changes membership; client refetches.

Jobs: instant placement (Rishi, on answer), day close (Kai runs, Rishi forms, Muse M3 batched theme grouping optional and off the player path).

Muse: none on this path. M3 only runs in the day-close batch and only affects grouping, never the response text.

Privacy
- Only for days the player answered; otherwise 404 `NOT_FOUND` (no leak of whether others answered).
- Star indices only, no ids, no labels, no shared-meaning text, no member answers.
- `answeredToday` is the only count. No percentages, no per-constellation sizes beyond `starIndices.length`.
- A constellation under 3 players is not returned (`placement: "pending"`, empty list).

Errors: `UNAUTHENTICATED`, `NOT_FOUND`, `CONSENT_REQUIRED`.

Empty: `constellations: []` with `placement: "ready"` is valid (nobody similar yet); UI shows the count only.

Backend owner: Rishi.

### S6. Your week, Mon-Fri

Purpose: show five days, which are answered, and which colors you have.

Reads
- `GET /cycles/:id/week` ->

```ts
interface WeekView {
  cycleId: Id;
  days: {
    day: 1 | 2 | 3 | 4 | 5;
    colorId: DayColorId;
    released: boolean;
    answered: boolean;
    isCatchUp: boolean;
    constellationCount: number;   // mine that day, 0 if unanswered
  }[];
}
```

Actions: none.

SSE: `daily.updated`, `day.closed`, `cycle.phase`.

Jobs: none beyond S5.

Muse: none.

Privacy: `constellationCount` counts only the viewer's own memberships. Unreleased days show `released: false` and no question text.

Errors: `UNAUTHENTICATED`, `NOT_FOUND`.

Backend owner: Will (days, answers), Rishi (counts).

### S7. Catch-up

Purpose: let the player answer missed days until Saturday lock.

Reads: `GET /cycles/current` -> `catchUp: { missedDays: number[]; closesAt: string }` (UTC, `closesAt` is Saturday 12:00 community time).

Actions: `POST /cycles/:id/answers` with `day` in `missedDays` (S3). Marked `isCatchUp: true`, lower weight, does not extend streak.

SSE: `cycle.phase` (lock).

Jobs: week lock (Kai).

Muse: none.

Privacy: a catch-up answer enters that day's constellations when the day is re-formed at the next close or at lock; it never changes what other players already saw that day except through `daily.updated`.

Errors: `CYCLE_LOCKED` after lock.

Backend owner: Will.

### S8. Streak and rewards

Purpose: show on-day streak and unlocked rewards.

Reads: `GET /cycles/current` -> `streak: { current: number; best: number; onDayDays: number[]; rewards: RewardId[] }`.

Actions: none.

SSE: `daily.updated` (streak changes after accepted answer).

Jobs: none. Streak is recomputed on answer accept (D008).

Muse: none.

Privacy: streaks are private to the player. No leaderboards, no counts of other players' streaks.

Errors: `UNAUTHENTICATED`.

Backend owner: Will.

### S9. Saturday sky (new)

Purpose: show the whole community sky with the player's week and second-degree constellations.

Reads
- `GET /cycles/:id/sky/stars` -> `{ weekSeed: string; count: number; positions: string }` where `positions` is base64 of `Int16Array` `[x0,y0,x1,y1,...]` on a fixed 0..32767 grid. About 40 KB for 10,000 stars. Public to joined players, same for all viewers, `Cache-Control: private, max-age=3600`.
- `GET /cycles/:id/sky/mine` ->

```ts
interface MySkyView {
  myStarIndex: number;
  mine: {
    constellationId: Id;
    day: 1 | 2 | 3 | 4 | 5;
    colorId: DayColorId;
    starIndices: number[];
  }[];
  secondDegree: {
    constellationId: Id;
    viaStarIndex: number;       // which of my constellation-stars it hangs from
    starIndices: number[];
  }[];                          // drawn at low opacity
}
```

Actions: none.

SSE: `cycle.phase` (lock moves to S10).

Jobs
- Week lock + sky layout (Saturday 12:00, Kai runs, Rishi lays out): deterministic force-free layout seeded by `weekSeed`, so all clients see the same positions. Stars are re-randomized every week.
- Second-degree (Rishi): for each star in my constellations (excluding me), its up to 2 biggest other constellations that week by size, excluding ones I am already in. Cap 40 constellations and 3,000 stars total per viewer; drop smallest first.

Muse: none.

Privacy
- Star indices only. `viaStarIndex` is an index, not an id. Second-degree constellations carry no color, day, size or label other than star indices.
- All 10,000 positions go to every viewer by design; positions reveal nothing about membership.
- A viewer never receives another viewer's `mine` set.
- Safety-flagged or deleted players are excluded from constellations; their star remains a plain star in `positions` (no hole that leaks deletion).

Errors: `NOT_FOUND` (before lock), `UNAUTHENTICATED`, `CONSENT_REQUIRED`.

Empty: `mine: []` if the player answered no day; `secondDegree: []` if cut (cut order 3) or no neighbors.

Backend owner: Rishi (data), Kai (route composition).

### S10. Forming / loading (new)

Purpose: show the algorithm trying connections one by one between Saturday sky and Sunday reveal.

Reads
- `GET /cycles/:id/formation/progress` -> `{ phase: "queued" | "running" | "done"; step: number; totalSteps: number; attempts: FormationAttempt[] }` (poll fallback).

```ts
interface FormationAttempt {
  seq: number;
  fromStarIndex: number;      // always one of the viewer's own stars or its neighbors
  toStarIndex: number;
  outcome: "tried" | "kept" | "dropped";
}
```

Actions: none.

SSE: `formation.progress` carries the next `FormationAttempt[]` slice (rate limited to 5 events/s) and `main.revealed` when done. `Last-Event-ID` resumes.

Jobs: main formation (Kai runs, Rishi forms). The stream replays a trace of real candidate pairs the algorithm evaluated for the viewer (the baseline matcher records these), paced for display. If trace recording is cut, the stream is a labeled visualization (`isVisualization: true`).

Muse: M4 (main constellation refinement) may run in the job; the stream never waits for it and never carries Muse text.

Privacy
- Only pairs involving the viewer's own star or their neighbors in S9's second-degree set are streamed. Pairs between two strangers never leave the server.
- Outcomes do not disclose scores or reasons.

Errors: `NOT_FOUND` (cycle not locked), `UNAUTHENTICATED`.

Edge: if formation finishes early, emit `done` and wait for Sunday 10:00 unless operator reveals; if it fails, `phase: "running"` stays and the operator retry (S15) is available; the player sees no error text.

Backend owner: Rishi (trace), Kai (stream).

### S11. Sunday main constellation, Meta logo reveal (new)

Purpose: reveal the player's closest people as one group drawn as the Meta logo.

Reads
- `GET /cycles/:id/main` ->

```ts
interface MainConstellationView {
  constellationId: Id;
  roomId: Id;
  myStarIndex: number;
  starIndices: number[];                         // 3-5 including me
  anchors: { index: number; t: number }[];       // t in 0..1 along the Meta-logo path, one per member
  brightness: Record<number, "bright" | "mid" | "faint">;
  revealedAt: string;
  roomExpiresAt: string;                         // revealedAt + 24 h
}
```

Actions: none.

SSE: `main.revealed` (Sunday 10:00, or operator).

Jobs
- Main constellation (Rishi): candidate set is players with 2+ shared constellations with the viewer that week (co-membership weight at least 2) or very similar answers (top-k by weighted similarity). Choose 3-5 including the viewer. One shared group: members are assigned by a greedy clique pass over the co-membership graph so every member has the others in their main constellation where possible; remaining conflicts resolve by highest total weight. A player belongs to exactly one main constellation. Players with no qualifying match get `null`.
- Meta-logo anchors (Rishi): each member gets `t` along a fixed logo polyline (infinity-shaped loop) in stable order by a per-week hash, so the UI draws the same logo.
- Reveal (Kai, Sunday 10:00): publishes views, opens room, schedules expiry.

Muse: M4 may refine ties only (Adam adapter). No Muse text reaches the player. No shared-meaning sentence is returned in v3.

Privacy
- Star indices and anchors only. No names, no shared-meaning text, no scores.
- Group size 3-5 is enforced by code; below 3 -> `main: null` and the player gets a fallback state, never a padded group with synthetic stars (synthetic players count only in fixture mode and are labeled in the operator view).
- Brightness is banded per viewer; raw score never sent.

Errors: `NOT_FOUND` (before reveal), `UNAUTHENTICATED`.

Empty: `main: null` with `reason: "no_match" | "opted_out" | "no_answers"` (enum, no detail).

Backend owner: Rishi.

### S12. 24-hour anonymous chat, report, block, mutual reveal

Purpose: let the main constellation talk anonymously for 24 hours.

Reads
- `GET /cycles/:id/room` -> `ChatRoom` `{ roomId, openedAt, expiresAt, members: { handle: AnonymousHandle; isMe: boolean }[] }`. No title, no name.
- `GET /rooms/:id/messages?after=<seq>` -> `ChatMessage[]` visible to the viewer (hidden-by-me and removed messages excluded).
- `GET /stream` SSE.

Actions
- `POST /rooms/:id/messages` body `{ text: string /* 1-500 */ }` -> `ChatMessage`. M1 + OutputGuard at submit. 422 `MESSAGE_REJECTED` with a generic message, no reason detail.
- `POST /rooms/:id/reports` body `{ messageId?: Id, handle: AnonymousHandle, reason: ReportReason }` -> 204. Message hidden for the reporter now, queued for the operator (S15).
- `POST /me/blocks` body `{ roomId, handle }` -> 204. Blocked handle's messages hidden for me; no existence leak.
- `POST /rooms/:id/reveal` body `{ toHandle }` -> `{ result: "pending" | "revealed" }`. Identity (`displayName`) revealed to both only when both have asked, and only inside this room's view.

SSE: `chat.message`, `chat.message_removed`, `chat.reveal` `{ result }`, `chat.expired`, `chat.member_left`.

Jobs: room expiry at `roomExpiresAt` (Kai): marks room closed, stops writes (410 `ROOM_EXPIRED`), deletes reveal state, schedules message deletion (Patrik). Muse nudge messages are removed in v3 (events use S13).

Muse: none on the send path except M1 (Patrik) and OutputGuard code check. No Muse-authored chat messages.

Privacy
- Handles are per-room random; same player has different handles in different rooms.
- Mutual reveal state is visible only to the two parties. A pending request is never shown to the target until they request too.
- Reports and blocks never notify the other party.
- Removing a member (operator) ends their writes and hides their messages for everyone.
- After expiry, nothing is readable by players.

Errors: `ROOM_EXPIRED` (410), `MESSAGE_REJECTED` (422), `FORBIDDEN` (not a member), `RATE_LIMITED` (messages: 10 per minute), `CONSENT_REQUIRED` (`anonymousChat` off).

Edge: `anonymousChat` off at join -> `main` is still shown, `room: null`; revoking consent mid-room leaves the room and hides prior messages for others only after Patrik's policy (not instantly deleted).

Backend owner: Kai (rooms, SSE), Patrik (M1, OutputGuard, blocks).

### S13. Events list and event nudge

Purpose: show approved events and nudge a player toward events where people from their constellations are going.

Reads
- `GET /events` -> `EventView[]` from the approved catalog only.
- `GET /events/:eventId` -> `EventView`.
- `GET /me/nudges` -> `EventNudge[]` (at most 2 active).

```ts
interface EventView {
  eventId: Id;                       // in Adam's allowlist
  title: string;
  placeId: Id;                       // approved public venue
  startsAt: string;
  endsAt: string;
  constellationInterestBucket: "none" | "3-5" | "6-10" | "11+";
  myInterest: boolean;
  kind: "catalog" | "custom";
}
interface EventNudge {
  nudgeId: Id;
  eventId: Id;
  copy: string;                      // Adam M7, templated, validated
  interestBucket: "3-5" | "6-10" | "11+";
  expiresAt: string;
}
```

Actions
- `PUT /events/:eventId/interest` body `{ interested: boolean }` -> `EventView`. Requires `eventSignals` consent. Stored privately (Patrik).
- `POST /nudges/:nudgeId/dismiss` -> 204.

SSE: `event.nudge` `{ nudgeId }`.

Jobs
- Constellation-interest counts (Rishi, hourly and on interest change): for each event, count distinct interested players who share at least one constellation this week with the viewer (computed per viewer, not stored globally). Bucketed, shown only when at least 3, otherwise `"none"`.
- Nudge eligibility (Rishi): viewer has `eventSignals`, bucket is at least `3-5`, event is upcoming within 7 days, viewer has not dismissed it, max 2 nudges per week.
- Nudge copy (Adam, M7): one sentence from a template plus event title, e.g. "People from your constellations are going to Open mic." Validated by OutputGuard (no names, no counts other than the bucket, no venue not in catalog). Failure falls back to the fixed template.
- Delivery (Kai): in-feed card and notification.

Muse: M7 for copy only, off the request path (precomputed by the job). Player-facing GET never calls Muse.

Privacy
- Never reveals who is going, never which constellation, never exact counts, never a count under 3.
- Interest is private; there is no attendee list.
- `eventId` must be in the allowlist; unknown ids -> 404.
- Nudges require `eventSignals`; revoking deletes queued nudges.
- Venues are approved public places only.

Errors: `CONSENT_REQUIRED`, `NOT_FOUND`, `RATE_LIMITED`.

Empty: `[]` events or `constellationInterestBucket: "none"` is normal.

Backend owner: Adam (catalog, copy), Rishi (counts, eligibility), Patrik (interest storage), Kai (delivery).

### S14. Custom event invite and RSVP (new)

Purpose: every few weeks, invite clusters of repeated constellation matches to a generated public-venue event.

Reads
- `GET /me/invites` -> `Invite[]` (own only).

```ts
interface Invite {
  inviteId: Id;
  event: EventView;                  // kind: "custom"
  rsvp: "none" | "going" | "not_going";
  status: "pending" | "confirmed" | "cancelled";
  confirmAtCount: 3;
}
```

Actions
- `PUT /invites/:inviteId/rsvp` body `{ rsvp: "going" | "not_going" }` -> `Invite`. Requires `eventSignals`.

SSE: `invite.created`, `invite.updated` (confirmed or cancelled).

Jobs
- Cluster finder (Rishi, every 2-3 weeks at week close): find groups of 6-30 players with repeated co-membership across the last N weeks (pairwise weight at least 3). Output: `clusterId` (internal), `clusterSize`, aggregate interest tags (allowlisted topics only), candidate time windows. Never player ids to Muse.
- Proposal (Adam, M7 `custom_event`): Muse receives only tags, size bucket, city-level area, time windows and the approved venue list; returns `CustomEventProposal`. Output validated against schema and catalog.
- Approval: operator approves or rejects in S15. Only approved proposals create `Invite`s for cluster members who have `eventSignals`.
- Confirmation (Patrik stores, Kai runs): confirmed when RSVPs reach 3 going, cancelled 24 h before start if under 3. Players are told only `status`.

Muse: M7 `custom_event` (Adam), operator-gated. No player-facing path calls Muse.

Privacy
- Cluster membership is never disclosed, not even size beyond the `confirmAtCount` rule. RSVP counts are never sent to players.
- Venue must be a public place from the approved catalog; no private addresses, no free-text locations from Muse.
- RSVP is private; no attendee list.
- Invites are issued only to players with `eventSignals`, adults, and not blocked in any shared room.

Errors: `CONSENT_REQUIRED`, `NOT_FOUND`, `STALE_REVISION`, `FORBIDDEN`.

Edge: cancelled event -> `status: "cancelled"` and no further RSVP (409 `STALE_REVISION`).

Backend owner: Rishi (cluster), Adam (proposal), Patrik (RSVP), Kai (confirmation job).

### S15. Operator console

Purpose: run the week, inspect formation, moderate, approve events, see Muse evidence.

Auth: `isOperator` on session, `FORBIDDEN` otherwise. All routes under `/operator`.

Reads and actions

| Panel | Route | Request / response | Owner |
| --- | --- | --- | --- |
| Cycle | `POST /operator/cycles` | -> `WeeklyCycle` (open, day 1) | Will |
| Cycle | `GET /operator/cycles/:id` | -> `WeeklyCycle`, `answeredToday`, `placementQueueDepth`, per-day totals | Will |
| Close day | `POST /operator/cycles/:id/close-day` body `{ day }` | -> 202 `{ jobId }`; runs day-close formation, emits `day.closed` | Will (control), Kai (job), Rishi (form) |
| Advance | `POST /operator/cycles/:id/advance` body `{ to?: "day"|"lock"|"reveal"|"close" }` | -> `WeeklyCycle`; demo timing | Will |
| Seed | `POST /operator/cycles/:id/synthetic-topup` | adds labeled synthetic players and answers from fixtures | Will |
| Reset | `POST /operator/cycles/:id/reset` | fixture cycles only | Will |
| Questions | `GET /operator/questions`, `POST /operator/questions/generate`, `POST /operator/cycles/:id/select-week` | as in API.md | Adam |
| Formation debug | `GET /operator/cycles/:id/formation-debug` | -> baseline vs Muse grouping, ids only, never shown outside operator; includes day clusters, co-membership summary, main constellation sizes, unmatched count | Rishi |
| Form / retry | `POST /operator/cycles/:id/form` | -> 202; reruns main formation | Kai, Rishi |
| Nudge panel | `GET /operator/events/nudges`, `POST /operator/events/:eventId/nudge-preview` | -> eligible counts per bucket, copy preview, OutputGuard verdict; no player ids | Adam, Rishi |
| Custom-event queue | `GET /operator/custom-events` | -> `CustomEventProposal[]` pending | Adam |
| Custom-event queue | `POST /operator/custom-events/:proposalId/decision` body `{ decision: "approve"|"reject", note? }` | -> `CustomEventProposal` | Adam |
| Report queue | `GET /operator/reports`, `POST /operator/reports/:id/action` body `{ action: "dismiss"|"remove_message"|"remove_member" }` | -> `Report` | Kai, Patrik |
| Muse calls | `GET /operator/calls` | -> `MuseCallEvidence[]` (model, callType, latency, live/replay, validation outcome, no prompts) | Adam |
| Jobs | `GET /operator/jobs` | -> `JobRun[]` (name, state, startedAt, duration, error code) | Kai |

SSE: operator stream carries `job.updated`, `report.created`, `proposal.created`.

Privacy
- Operator sees ids only where the existing Exposure rule allows (formation debug). Never another player's answer text.
- Synthetic players are labeled on every operator projection and cannot appear in real players' views.
- Every operator action is audit-logged (actor, route, timestamp).

Errors: `FORBIDDEN`, `NOT_FOUND`, `STALE_REVISION`, `IDEMPOTENCY_CONFLICT`, `PROVIDER_UNAVAILABLE`.

Backend owner: Will (controls), Kai (composition).

### R1-R3. Removed screens

| Removed | Backend actions |
| --- | --- |
| R1 Prevalence guess card | Remove `PUT /cycles/:id/guess`, `Guess` storage, `PrevalenceGuess`, M8 guess/theme stats. Migration deletes stored guesses (Patrik). |
| R2 Sky statistics and percentages | Remove `GET /cycles/:id/sky`, `SkyStats`, `SkyTheme`, `computeSky` stats path, M5 naming, M8 Sky narration. Replaced by S9 endpoints. |
| R3 Constellation names | Remove `Constellation.name`, `shapeId`, M3 naming output, room title. `constellationId` is opaque. |

## 5. Realtime events (`GET /stream`)

Filtered per player. `Last-Event-ID` resumes. Event ids are monotonic per player.

| Event | Payload | Emitted when | Screens |
| --- | --- | --- | --- |
| `cycle.phase` | `{ cycleId, phase }` | open, lock, forming, reveal, close | S0, S6, S7, S9, S10 |
| `daily.updated` | `{ day }` | placement ready or day close changed membership | S0, S3, S5, S6, S8 |
| `day.closed` | `{ day }` | day-close formation committed | S6 |
| `formation.progress` | `{ step, totalSteps, attempts }` | during main formation | S10 |
| `main.revealed` | `{ roomId }` | Sunday reveal | S10, S11 |
| `chat.message`, `chat.message_removed`, `chat.reveal`, `chat.expired`, `chat.member_left` | as 2.x | room activity | S12 |
| `event.nudge` | `{ nudgeId }` | nudge created | S13 |
| `invite.created`, `invite.updated` | `{ inviteId }` | custom event invite or status change | S14 |

## 6. Jobs

| Job | Trigger | Runs / forms | Muse | Output |
| --- | --- | --- | --- | --- |
| Instant placement | answer accepted | Kai runs, Rishi forms | none | player's day constellations, `daily.updated` |
| Day close | operator or midnight community time, Mon-Fri | Kai runs, Rishi forms | M3 batched, optional | final day clusters, `day.closed`, co-membership graph update |
| Co-membership graph | after each day close | Rishi | none | weekly edge weights (server only) |
| Week lock + sky layout | Saturday 12:00 | Kai runs, Rishi lays out | none | positions, second-degree sets, `cycle.phase` |
| Main formation | after lock | Kai runs, Rishi forms | M4 optional | main constellations, anchors, progress trace |
| Formation progress stream | during main formation | Kai | none | `formation.progress` |
| Reveal | Sunday 10:00 | Kai | none | `main.revealed`, room open |
| Room expiry | reveal + 24 h | Kai | none | room closed, deletion scheduled |
| Event interest counts | interest change, hourly | Rishi | none | per-viewer buckets, nudge eligibility |
| Event nudges | after counts | Adam copy, Kai delivery | M7 | `EventNudge`, `event.nudge` |
| Custom-event cluster finder | week close, every 2-3 weeks | Rishi | none | clusters (internal) |
| Custom-event proposals | after cluster finder | Adam | M7 `custom_event` | `CustomEventProposal` pending approval |
| Custom-event confirmation | RSVP change, T-24 h | Kai | none | `confirmed` at 3 going, else `cancelled` |
| Retention | daily | Patrik | none | deletes per policy |

Latency budget: nothing on a player-facing GET waits on Muse. Instant placement p95 under 1.5 s with the baseline matcher at 10,000 players (incremental index). Every job rechecks consent and membership before executing.

## 7. Contract 3.0.0 type sketch

Breaking vs 2.1.0; all five owners ACK in `docs/DECISIONS.md` (D012).

```ts
export const CONTRACT_VERSION = "3.0.0";

export type DayColorId = "blue" | "teal" | "green" | "amber" | "rose";  // Mon..Fri
export type Day = 1 | 2 | 3 | 4 | 5;

// Removed: SkyStats, SkyTheme, SyntheticSignal (player-facing), PrevalenceGuess,
// M5In/M5Out, M8In/M8Out, Constellation.name, Constellation.shapeId, ChatRoom.title.

export interface ConsentToggles {
  anonymousChat: boolean;
  useActivity: boolean;
  voiceInput: boolean;
  eventSignals: boolean;                 // new
}

export interface WeeklyCycle {
  id: Id;
  phase: "open" | "locked" | "forming" | "revealed" | "closed";
  currentDay: Day | null;
  answeredToday: number;                 // new
  lockAt: string;
  revealAt: string;
}

export interface CurrentCycleView {
  cycle: WeeklyCycle | null;
  today: DailyQuestion | null;
  streak: Streak;
  catchUp: CatchUpState;
}

export interface DailyConstellationsView { /* section S5 */ }
export interface WeekView { /* section S6 */ }
export interface SkyStarsView { weekSeed: string; count: number; positions: string; }
export interface MySkyView { /* section S9 */ }
export interface FormationAttempt { /* section S10 */ }
export interface MainConstellationView { /* section S11 */ }

export interface ChatRoom {
  roomId: Id;
  openedAt: string;
  expiresAt: string;
  members: { handle: AnonymousHandle; isMe: boolean }[];   // no title
}

export interface EventView { /* section S13 */ }
export interface EventNudge { /* section S13 */ }

export interface CustomEventProposal {
  proposalId: Id;
  clusterSize: number;                   // operator only
  title: string;
  why: string;                           // tags only, no player text
  placeId: Id;                           // approved public venue
  timeWindow: { startsAt: string; endsAt: string };
  evidence: MuseCallEvidence;
  status: "pending" | "approved" | "rejected";
}

export interface Invite {
  inviteId: Id;
  event: EventView;
  rsvp: "none" | "going" | "not_going";
  status: "pending" | "confirmed" | "cancelled";
}

export type StreamEvent =
  | /* 2.x events */
  | { type: "daily.updated"; day: Day }
  | { type: "day.closed"; day: Day }
  | { type: "formation.progress"; step: number; totalSteps: number; attempts: FormationAttempt[] }
  | { type: "main.revealed"; roomId: Id }
  | { type: "event.nudge"; nudgeId: Id }
  | { type: "invite.created" | "invite.updated"; inviteId: Id };

export type ErrorCode = /* 2.x codes, unchanged */;
```

Fixtures to add under `contracts/fixtures/`: daily-constellations, week, sky-stars (small), my-sky, formation-progress, main, event-nudge, invite, custom-event-proposal.

## 8. Privacy rules (server enforced)

1. Stars on the wire are week-randomized indices, never player ids. Re-randomized every cycle.
2. No constellation, room or chat title carries a name or label. No shared-meaning text player-facing.
3. Only the owner reads their `DailyAnswer`, follow-up, interest or RSVP.
4. The only shared number on daily screens is `answeredToday`. No percentages, no prevalence, no per-constellation stats.
5. Second-degree sets contain star indices only and are computed per viewer.
6. Main constellation is 3-5 players enforced by code; below 3 returns null, no padding with synthetic stars.
7. Chat handles are per room; mutual reveal only when both ask, only inside the room; reports and blocks never notify the other party.
8. Event counts are bucketed and only shown at 3 or more. Never who, never which constellation.
9. Event signals require `eventSignals` consent; revocation deletes interests, RSVPs and queued nudges and invites.
10. Custom events use approved public venues only, confirmed at 3 or more RSVPs, operator approved before any invite.
11. Muse never sees player ids, names, emails or raw answers for event and cluster work; only allowlisted tags and buckets. Muse is not called on any player-facing GET.
12. Every chat message passes M1 and OutputGuard; safety-flagged content never reaches a game output.
13. Consent and membership are rechecked before every queued job runs.
14. `DELETE /me/data` removes the player from all pending sets and future jobs; idempotent.
15. Operator views label synthetic players and never expose another player's answer text. Operator actions are audit logged.
16. Rooms expire 24 h after reveal; after expiry nothing is readable.

## 9. Cut order

Freeze at 04:30 AM PST Nov 13. If behind, cut in this order (earlier items go first):

1. Custom events: keep proposal and operator approval only; drop invites, RSVP and confirmation (S14 becomes operator-only).
2. Formation progress stream (S10): fall back to a labeled visualization (`isVisualization: true`), no real trace.
3. Second-degree constellations (S9): `secondDegree: []`, own constellations only.
4. Instant placement: placement at day close only; operator "close day" in the demo. S5 shows after close.

Never cut: anonymity (no names, ids, labels), consent, safety screening (M1), OutputGuard, 24 h expiry, mutual reveal rules, truth labels for fixtures and replays.

## 10. Backend owner summary

| Owner | Owns |
| --- | --- |
| Rishi | instant daily placement, day-close formation, co-membership graph, main constellation and Meta-logo anchors, sky layout and second-degree, formation progress stream, event constellation-interest counts and nudge eligibility, custom-event cluster finder, contract 3.0.0 draft |
| Adam | Muse adapter, question bank and selection, follow-up (M2), event catalog with `eventId` allowlist, nudge copy (M7), `custom_event` proposals (M7) |
| Will | cycle and day state, answers, streaks, `answeredToday`, operator controls (close day, advance, seed, reset) |
| Patrik | sessions and consent (adds `eventSignals`), private answer, interest and RSVP storage, safety M1, OutputGuard, retention, blocks |
| Kai | API composition, job runner (day close, lock, reveal, expiry, confirmation), 24 h chat, SSE, sky and stars endpoint composition |

Screens by backend owner: Rishi S5 S9 S10 S11 (S13 counts, S14 cluster); Adam S4 S13 S14; Will S0 S3 S6 S7 S8 S15; Patrik S1 S2 (S12 safety); Kai S12 and all composition.
