/*
 * Space home. One quiet page: the sky and week tracker, a title line, tabs, then
 * flat sections on the page itself (today's question, this week, weekend) with
 * hairline rhythm instead of stacked cards, and a plain-text side column.
 */
import { useState, type ReactNode } from "react";
import { CalendarDays, ChevronRight, Flame, Lock, MessageCircle } from "lucide-react";
import type { CycleClient, CycleDay, DailyQuestion } from "../client";
import { MAX_CHARS } from "../useDaily";
import { DAY_LONG, DAY_SHORT, type Screen, type WeekModel } from "./model";
import { MicIcon, Waveform } from "./parts";
import SkyCanvas from "./SkyCanvas";
import { useVoiceInput } from "./useVoiceInput";
import { useAnsweredToday } from "./stats";

type Go = (screen: Screen, day?: number) => void;

// One straight week strip. Only released question text is exposed.
export function DayTracker({ week, go, question }: { week: WeekModel; go: Go; question: (d: number) => DailyQuestion | undefined }) {
  return (
    <div className="spc-week-strip" role="list" aria-label="Your week">
      {DAY_SHORT.map((label, i) => {
        const day = i + 1;
        const answered = week.answered.has(day);
        const catchUp = day < week.day && day <= 5 && week.day <= 5 && !answered;
        const status = answered ? (week.answers.get(day)?.isCatchUp ? "Caught up" : "Answered") : day === week.day ? "Today" : catchUp ? "Catch up" : day > week.day ? "Not yet" : "Missed";
        const text = day <= 5 && day <= week.day ? question(day)?.question.text : undefined;
        const action = answered ? () => go("daily", day) : catchUp ? () => go("answer", day) : day >= 6 && week.day >= day ? () => go(day === 6 ? "sky" : "main") : null;
        const inside = <><span className={`spc-week-check${answered ? " is-done" : ""}${day === week.day ? " is-today" : ""}`} aria-hidden="true">{answered ? "✓" : day}</span><span>{label}</span></>;
        return <div className="spc-week-item" role="listitem" key={day} data-testid={`spc-week-${day}`}>
          {action ? <button type="button" aria-label={`${DAY_LONG[i]}: ${status}`} aria-describedby={`spc-day-tip-${day}`} onClick={action} data-testid={catchUp ? `spc-catchup-${day}` : undefined}>{inside}</button> : <span className="spc-week-static" tabIndex={0} aria-label={`${DAY_LONG[i]}: ${status}`} aria-describedby={`spc-day-tip-${day}`}>{inside}</span>}
          <span className="spc-week-tip" role="tooltip" id={`spc-day-tip-${day}`}><b>{DAY_LONG[i]} · {status}</b>{text ?? (day === 6 ? "Your week’s sky" : day === 7 ? "Your constellation reveal" : "Question opens on this day.")}</span>
        </div>;
      })}
    </div>
  );
}

// ---------------------------------------------------------------- today's question post
function QuestionPost({
  client,
  week,
  day,
  text,
  go,
  onPost,
  busy,
  error,
}: {
  client: CycleClient;
  week: WeekModel;
  day: CycleDay;
  text: string;
  go: Go;
  onPost: (day: CycleDay, text: string, source: "voice" | "text") => Promise<void>;
  busy: boolean;
  error: string | null;
}) {
  const [draft, setDraft] = useState("");
  const [releasing, setReleasing] = useState<string | null>(null);
  const voice = useVoiceInput(client, setDraft);
  const answer = week.answers.get(day);
  const post = async () => {
    const t = draft.trim();
    if (!t || busy || releasing) return;
    setReleasing(t);

    try {
      await onPost(day, t, voice.source);
      setDraft("");
      voice.reset();
    } catch {
      /* the parent shows the error; the draft stays */
    } finally {
      setReleasing(null);
    }
  };
  return (
    <section className="spc-block spc-today" aria-labelledby="spc-today-q" data-testid="spc-today">
      <p className="spc-kicker">
        {DAY_LONG[day - 1]} · Today’s question
        <span className="spc-kicker-private">
          <Lock size={12} aria-hidden="true" /> Only you
        </span>
      </p>
      <p id="spc-today-q" className="spc-today-question">{text}</p>
      {!answer ? (
        <>
          <div className="spc-composer">
            {voice.recording ? (
              <div className="spc-listening">
                <Waveform />
                {draft ? (
                  <p className="spc-live-text" aria-live="polite">
                    {draft}
                  </p>
                ) : (
                  <span>Listening… take your time</span>
                )}
              </div>
            ) : (
              <textarea
                aria-label="Your answer"
                value={draft}
                maxLength={MAX_CHARS}
                disabled={Boolean(releasing)}
                onChange={(e) => setDraft(e.target.value.slice(0, MAX_CHARS))}
              />
            )}

          </div>
          <div className="spc-composer-row">
            <button
              type="button"
              className={`spc-mic${voice.recording ? " is-on" : ""}`}
              onClick={voice.toggle}
              disabled={voice.blocked}
              aria-label={voice.recording ? "Stop recording" : "Answer by voice"}
              aria-pressed={voice.recording}
            >
              <MicIcon />
            </button>
            <span className="spc-hint" aria-live="polite">
              {voice.hint}
            </span>
            <button type="button" className="spc-btn spc-btn-primary" disabled={!draft.trim() || busy || Boolean(releasing)} onClick={() => void post()}>
              {busy || releasing ? "Saving…" : "Post privately"}
            </button>
          </div>
          {error && (
            <p className="spc-error" role="alert">
              {error}
            </p>
          )}
        </>
      ) : (
        <>
          <figure className="spc-mine">
            <blockquote>{answer.text}</blockquote>
            <figcaption>
              <Lock size={11} aria-hidden="true" /> Only you. You answered today.
            </figcaption>
          </figure>
          <div className="spc-row">
            <button type="button" className="spc-btn spc-btn-primary spc-grow" onClick={() => go("daily", day)}>
              See today's stars
            </button>
            <button type="button" className="spc-btn spc-btn-gray" onClick={() => go("answer", day)}>
              Edit
            </button>
          </div>
        </>
      )}
    </section>
  );
}

// ---------------------------------------------------------------- stats
function StatsCard({ answered, count }: { answered: boolean; count: number | null }) {
  return (
    <section className="spc-side-block spc-stats" aria-labelledby="spc-stats-title" data-testid="spc-stats">
      <h3 id="spc-stats-title">Today in the sky</h3>
      <p className="spc-stat-line">
        {answered ? (
          <>
            {count !== null ? <><b data-testid="spc-stat-count">{count.toLocaleString()}</b><span>people answered</span></> : <span>Today’s answer count is unavailable.</span>}
          </>
        ) : (
          <span>Answer to see how many people answered.</span>
        )}
      </p>
    </section>
  );
}

// ---------------------------------------------------------------- page
export function SkyHome({
  client,
  week,
  question,
  cycleId,
  go,
  onPost,
  busy,
  error,
  fixture,
  chatOn,
  eventsOn,
  demoTiming,
  demo,
}: {
  client: CycleClient;
  week: WeekModel;
  question: (d: number) => DailyQuestion | undefined;
  cycleId: string;
  go: Go;
  onPost: (day: CycleDay, text: string, source: "voice" | "text") => Promise<void>;
  busy: boolean;
  error: string | null;
  fixture: boolean;
  chatOn: boolean;
  eventsOn: boolean;
  demoTiming: boolean;
  demo: ReactNode;
}) {
  const today = week.today;
  const q = today ? question(today) : undefined;
  const answeredToday = today ? week.answered.has(today) : false;
  const statsDay = (today ?? 5) as CycleDay;
  const count = useAnsweredToday(client, cycleId, today, today ? (week.answers.get(today)?.answerId ?? null) : null);
  const sunday = week.day >= 7;
  const tabs: { label: string; to: Screen; on?: boolean }[] = [
    { label: "Today", to: "home", on: true },
    { label: "Week sky", to: "sky" },
    ...(sunday ? [{ label: "Constellation", to: "main" as Screen }] : []),
    ...(sunday && eventsOn ? [{ label: "Events", to: "events" as Screen }] : []),
    { label: "Privacy", to: "settings" },
  ];

  return (
    <div className="spc-home" data-testid="spc-home">
      <header className="spc-cover">
        <div className="spc-cover-sky">
          <SkyCanvas input={{ mode: "home", answered: week.answered, viewDay: statsDay, emptyDay: false, noMatch: false }} />
        </div>
        <div className="spc-cover-id">
          <div className="spc-grow">
            <h1 className="spc-cover-title">
              Facebook Space<span className="sr-only"> · Space</span>
            </h1>
            <p className="spc-cover-sub">
              A weekly game. Answers stay private; matching is anonymous.
            </p>
            {fixture && (
              <span className="spc-mode" data-testid="cst-mode">
                Fixture mode · no server, no Muse
              </span>
            )}
          </div>
          {week.streak > 0 && (
            <span className="spc-streak-chip" title="Days in a row answered on the day">
              <Flame size={14} aria-hidden="true" /> {week.streak}-day streak
            </span>
          )}
        </div>
        <nav className="spc-tabs" aria-label="Space sections">
          {tabs.map((t) => (
            <button type="button" key={t.label} className={`spc-tab${t.on ? " is-active" : ""}`} aria-current={t.on ? "page" : undefined} onClick={() => go(t.to)}>
              {t.label}
            </button>
          ))}
        </nav>
      </header>

      <div className="spc-cols">
        <div className="spc-col-main">
          {q && today && (
            <QuestionPost
              key={`${cycleId}:${today}`}
              client={client}
              week={week}
              day={today}
              text={q.question.text}
              go={go}
              onPost={onPost}
              busy={busy}
              error={error}
            />
          )}

          <section className="spc-block spc-week-progress" aria-labelledby="spc-week-title">
            <h3 id="spc-week-title" className="spc-block-title">This week</h3>
            <DayTracker week={week} go={go} question={question} />
            {week.catchUps.length > 0 && <p className="spc-fine">Select a missed day to catch up before Saturday noon.</p>}
          </section>

          {week.day === 6 && (
            <section className="spc-block spc-today" data-testid="spc-weekend-sat">
              <h2 className="spc-block-lead">Your week is in the sky</h2>
              <p className="spc-block-sub">Answers are locked. Your people are found Sunday at 10 AM.</p>
              <button type="button" className="spc-btn spc-btn-primary" onClick={() => go("sky")}>
                View sky
              </button>
            </section>
          )}
          {week.day === 7 && (
            <>
              <section className="spc-block spc-today" data-testid="spc-weekend-sun">
                <h2 className="spc-block-lead">Sunday&apos;s reveal is open</h2>
                <p className="spc-block-sub">See who answered like you this week.</p>
                <button type="button" className="spc-btn spc-btn-primary" onClick={() => go("main")}>
                  View constellation
                </button>
              </section>
              {(chatOn || eventsOn) && (
                <section className="spc-block spc-weeklist">
                  {chatOn && (
                    <button type="button" className="spc-list-row" onClick={() => go("chat")}>
                      <span className="spc-list-icon is-tint" aria-hidden="true">
                        <MessageCircle size={20} />
                      </span>
                      <span className="spc-list-main">
                        Chat
                        <small>Open for 24 hours</small>
                      </span>
                      <ChevronRight size={20} className="spc-chev" aria-hidden="true" />
                    </button>
                  )}
                  {eventsOn && (
                    <>
                      <button type="button" className="spc-list-row" onClick={() => go("events")}>
                        <span className="spc-list-icon is-tint" aria-hidden="true">
                          <CalendarDays size={20} />
                        </span>
                        <span className="spc-list-main">
                          Where your people are going
                          <small>Events from your constellation</small>
                        </span>
                        <ChevronRight size={20} className="spc-chev" aria-hidden="true" />
                      </button>
                      <button type="button" className="spc-list-row" onClick={() => go("invite")}>
                        <span className="spc-list-icon is-tint" aria-hidden="true">
                          <CalendarDays size={20} />
                        </span>
                        <span className="spc-list-main">
                          You're invited
                          <small>Invites from your constellation</small>
                        </span>
                        <span className="spc-unread" aria-label="New" />
                        <ChevronRight size={20} className="spc-chev" aria-hidden="true" />
                      </button>
                    </>
                  )}
                </section>
              )}
            </>
          )}
          {week.day >= 8 && (
            <section className="spc-block spc-empty" data-testid="spc-weekend-over">
              <h2>This week has ended</h2>
              <p className="spc-sub">A new week opens Monday morning.</p>
            </section>
          )}
          {demoTiming && (
            <p className="spc-fine spc-center">
              <span className="spc-preview">Demo timing</span> Days move when the operator advances them.
            </p>
          )}
        </div>
        <aside className="spc-col-side" aria-label="About this week">
          {week.day <= 5 && <StatsCard answered={answeredToday} count={count} />}
          {demo}
        </aside>
      </div>
    </div>
  );
}
