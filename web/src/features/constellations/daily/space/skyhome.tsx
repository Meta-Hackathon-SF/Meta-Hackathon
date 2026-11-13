/*
 * Space home, laid out like a Facebook Group page: a sky cover with the day
 * tracker, tabs, then separate cards (today's question, catch up, weekend) and a
 * side column (today's stats, about, demo controls).
 */
import { useRef, useState, type ReactNode } from "react";
import { CalendarDays, ChevronRight, Clock, Flame, Lock, MessageCircle, Users } from "lucide-react";
import Avatar from "../../../../components/common/Avatar";
import { currentUser } from "../../../../data/demo";
import type { CycleClient, CycleDay, DailyQuestion } from "../client";
import { MAX_CHARS } from "../useDaily";
import { DAY_LONG, DAY_SHORT, dayHex, type Screen, type WeekModel } from "./model";
import { MicIcon, PreviewTag, SpaceAvatar, StarField, Waveform } from "./parts";
import { PREVIEW_INVITE, PREVIEW_THINK } from "./preview";
import SkyCanvas from "./SkyCanvas";
import { useVoiceInput } from "./useVoiceInput";
import { fmtDuration, readTook, useAnsweredToday, writeTook } from "./stats";

type Go = (screen: Screen, day?: number) => void;

// ---------------------------------------------------------------- day tracker
const W = 360, H = 78;
const PTS = DAY_SHORT.map((_, i) => ({ x: 26 + i * 51.3, y: 34 + Math.sin(i * 1.25 + 0.6) * 14 }));
const path = (n: number) =>
  PTS.slice(0, n).reduce((a, p, i) => (i ? `${a} C ${PTS[i - 1].x + 20} ${PTS[i - 1].y}, ${p.x - 20} ${p.y}, ${p.x} ${p.y}` : `M${p.x} ${p.y}`), "");

export function DayTracker({ week, go }: { week: WeekModel; go: Go }) {
  return (
    <div className="spc-tracker" role="list" aria-label="Your week">
      <svg viewBox={`0 0 ${W} ${H}`} aria-hidden="true">
        <path d={path(7)} className="spc-tracker-all" />
        <path d={path(Math.max(1, Math.min(week.day, 7)))} className="spc-tracker-done" />
      </svg>
      {PTS.map((p, i) => {
        const d = i + 1;
        let cls = "is-future", status = "Not yet", action: (() => void) | null = null, style: React.CSSProperties = {};
        if (d <= 5) {
          const hex = dayHex(d);
          if (week.answered.has(d)) {
            cls = "is-done";
            status = week.answers.get(d)?.isCatchUp ? "Caught up" : "Answered";
            style = { background: hex, boxShadow: `0 0 12px ${hex}` };
            action = () => go("daily", d);
          } else if (d === week.day) {
            cls = "is-today";
            status = "Today";
            style = { borderColor: hex, boxShadow: `0 0 16px ${hex}` };
          } else if (d < week.day) {
            cls = "is-missed";
            status = week.day <= 5 ? "Catch up" : "Missed";
            if (week.day <= 5) action = () => go("answer", d);
          }
        } else if (week.day >= d) {
          cls = "is-weekend";
          status = d === 6 ? "Week sky" : "Constellation";
          action = () => go(d === 6 ? "sky" : "main");
        }
        const label = `${DAY_LONG[i]}: ${status}`;
        const inner = (
          <>
            <span className={`spc-node ${cls}`} style={style} />
            <span className={`spc-node-l${d === week.day ? " is-now" : ""}`}>{DAY_SHORT[i]}</span>
          </>
        );
        return (
          <div role="listitem" key={d} className="spc-tracker-item" style={{ left: `${(p.x / W) * 100}%`, top: `${(p.y / H) * 100}%` }} data-testid={`spc-week-${d}`}>
            {action ? (
              <button type="button" onClick={action} aria-label={label}>
                {inner}
              </button>
            ) : (
              <span aria-label={label}>{inner}</span>
            )}
          </div>
        );
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
  cycleId,
  go,
  onPost,
  busy,
  error,
  onTook,
}: {
  client: CycleClient;
  week: WeekModel;
  day: CycleDay;
  text: string;
  cycleId: string;
  go: Go;
  onPost: (day: CycleDay, text: string, source: "voice" | "text") => Promise<void>;
  busy: boolean;
  error: string | null;
  onTook: (s: number) => void;
}) {
  const [draft, setDraft] = useState("");
  const [releasing, setReleasing] = useState<string | null>(null);
  const started = useRef<number | null>(null);
  const voice = useVoiceInput(client, (t) => {
    started.current ??= Date.now();
    setDraft(t);
  });
  const answer = week.answers.get(day);
  const post = async () => {
    const t = draft.trim();
    if (!t || busy || releasing) return;
    const seconds = started.current ? (Date.now() - started.current) / 1000 : 0;
    if (seconds > 0) {
      writeTook(cycleId, day, seconds);
      onTook(seconds);
    }
    setReleasing(t);
    const reduce = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    try {
      await Promise.all([onPost(day, t, voice.source), new Promise((r) => window.setTimeout(r, reduce ? 0 : 1800))]);
      setDraft("");
      voice.reset();
      started.current = null;
    } catch {
      /* the parent shows the error; the draft stays */
    } finally {
      setReleasing(null);
    }
  };
  return (
    <section className="spc-card spc-today" aria-labelledby="spc-today-q" data-testid="spc-today">
      <div className="spc-post-head">
        <SpaceAvatar />
        <div>
          <div className="spc-post-name">Today's question</div>
          <div className="spc-post-meta">
            {DAY_LONG[day - 1]}
            {week.streak ? ` · ${week.streak}-day streak` : ""} · <Lock size={12} aria-hidden="true" /> Only you
          </div>
        </div>
      </div>
      <div className="spc-qcard">
        <StarField />
        <p id="spc-today-q">{text}</p>
      </div>
      {!answer ? (
        <>
          <div className="spc-composer">
            {voice.recording ? (
              <div className="spc-listening">
                <Waveform />
                <span>Listening… take your time</span>
              </div>
            ) : (
              <textarea
                aria-label="Your answer"
                value={releasing ? "" : draft}
                maxLength={MAX_CHARS}
                disabled={Boolean(releasing)}
                onFocus={() => (started.current ??= Date.now())}
                onChange={(e) => {
                  started.current ??= Date.now();
                  setDraft(e.target.value.slice(0, MAX_CHARS));
                }}
                placeholder="Say it to the sky. Nobody's reading this but you."
              />
            )}
            {releasing && (
              <div className="spc-float" aria-hidden="true">
                {releasing}
              </div>
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
              Post privately
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
          <div className="spc-comment">
            <Avatar person={currentUser} size={32} />
            <div>
              <div className="spc-comment-bubble">
                <b>{currentUser.name}</b>
                <span>{answer.text}</span>
              </div>
              <div className="spc-comment-meta">
                <Lock size={11} aria-hidden="true" /> Only you · You answered today
              </div>
            </div>
          </div>
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
function StatsCard({ day, answered, count, took }: { day: CycleDay; answered: boolean; count: number | null; took: number | null }) {
  const think = PREVIEW_THINK[day - 1];
  const max = Math.max(...think.buckets);
  const deep = think.buckets[2] + think.buckets[3];
  const verdict = deep >= 45 ? "People really thought about this one." : deep >= 30 ? "A good mix of quick and careful answers." : "Most people knew right away.";
  return (
    <section className="spc-card spc-side-card spc-stats" aria-labelledby="spc-stats-title" data-testid="spc-stats">
      <header className="spc-row spc-between">
        <h3 id="spc-stats-title">Today in the sky</h3>
        <span className="spc-stats-day">
          <i style={{ background: dayHex(day) }} />
          {DAY_LONG[day - 1]}
        </span>
      </header>
      <div className="spc-stats-tiles">
        <div className="spc-tile">
          <Users size={18} aria-hidden="true" />
          {answered ? (
            <>
              <b data-testid="spc-stat-count">{count !== null ? count.toLocaleString() : "—"}</b>
              <span>people answered</span>
            </>
          ) : (
            <>
              <b>?</b>
              <span>Answer to see how many</span>
            </>
          )}
        </div>
        <div className="spc-tile">
          <Clock size={18} aria-hidden="true" />
          <b>{fmtDuration(think.median)}</b>
          <span>typical time thinking</span>
        </div>
      </div>
      <div className="spc-think" aria-label="How long people took">
        {think.buckets.map((v, i) => (
          <div className="spc-think-col" key={i}>
            <div className="spc-think-bar">
              <i style={{ height: `${(v / max) * 100}%`, background: dayHex(day) }} />
            </div>
            <span>{["< 1m", "1–3m", "3–5m", "5m+"][i]}</span>
            <small>{v}%</small>
          </div>
        ))}
      </div>
      <p className="spc-stats-verdict">
        {verdict} {answered && took ? <b>You took {fmtDuration(took)}.</b> : null}
      </p>
      <PreviewTag>Time stats: preview</PreviewTag>
    </section>
  );
}

function AboutCard() {
  return (
    <section className="spc-card spc-side-card" aria-labelledby="spc-about-title">
      <h3 id="spc-about-title">About</h3>
      <ul className="spc-about">
        <li>
          <CalendarDays size={18} aria-hidden="true" />
          <span>
            <b>Mon–Fri: one question a day</b>
            <small>Type or talk. Missed one? Catch up until Saturday noon.</small>
          </span>
        </li>
        <li>
          <Users size={18} aria-hidden="true" />
          <span>
            <b>Sunday: meet your people</b>
            <small>3–5 people whose answers meant the same thing.</small>
          </span>
        </li>
        <li>
          <Lock size={18} aria-hidden="true" />
          <span>
            <b>Private by default</b>
            <small>Nobody reads your answers. Names show only if you both reveal.</small>
          </span>
        </li>
      </ul>
    </section>
  );
}

// ---------------------------------------------------------------- this week
function WeekList({ week, question, go }: { week: WeekModel; question: (d: number) => DailyQuestion | undefined; go: Go }) {
  const days = ([1, 2, 3, 4, 5] as CycleDay[]).filter((d) => d !== week.today);
  return (
    <section className="spc-card spc-list spc-weeklist" aria-labelledby="spc-week-title" data-testid="spc-weeklist">
      <h3 id="spc-week-title" className="spc-list-title">
        This week
      </h3>
      {days.map((d) => {
        const a = week.answers.get(d);
        const q = question(d);
        const released = week.day > d || (week.day <= 5 && d <= week.day);
        const canCatchUp = !a && week.day <= 5 && d < week.day;
        const status = a ? (a.isCatchUp ? "Caught up" : "Answered") : canCatchUp ? "Catch up" : released ? "Missed" : `Opens ${DAY_LONG[d - 1]}`;
        const badgeCls = a ? "" : canCatchUp ? " is-open" : " is-future";
        const body = (
          <>
            <span className={`spc-day-badge${badgeCls}`} style={{ background: dayHex(d), color: a ? "#fff" : dayHex(d) }} aria-hidden="true">
              {a ? "✓" : DAY_SHORT[d - 1]}
            </span>
            <span className="spc-list-main">
              <b>{DAY_LONG[d - 1]}</b>
              {released && q ? q.question.text : "Question not out yet"}
            </span>
            <span className={`spc-status-pill${a ? " is-done" : canCatchUp ? " is-action" : ""}`}>{canCatchUp ? "Answer" : status}</span>
          </>
        );
        if (canCatchUp)
          return (
            <button type="button" key={d} className="spc-list-row" onClick={() => go("answer", d)} data-testid={`spc-catchup-${d}`} aria-label={`Catch up: ${DAY_LONG[d - 1]}'s question`}>
              {body}
            </button>
          );
        if (a)
          return (
            <button type="button" key={d} className="spc-list-row" onClick={() => go("daily", d)} aria-label={`${DAY_LONG[d - 1]}: ${status}. See that day's stars`}>
              {body}
            </button>
          );
        return (
          <div key={d} className="spc-list-row is-static">
            {body}
          </div>
        );
      })}
      {week.catchUps.length > 0 && <p className="spc-fine spc-weeklist-foot">Catch-ups close Saturday at noon. They don't extend your streak.</p>}
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
  const [took, setTook] = useState<number | null>(() => (today ? readTook(cycleId, today) : null));
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
      <header className="spc-card spc-cover">
        <div className="spc-cover-sky">
          <SkyCanvas input={{ mode: "home", answered: week.answered, viewDay: statsDay, emptyDay: false, noMatch: false }} />
          <DayTracker week={week} go={go} />
        </div>
        <div className="spc-cover-id">
          <SpaceAvatar size={64} />
          <div className="spc-grow">
            <h1 className="spc-cover-title">
              Facebook Space<span className="sr-only"> · Space</span>
            </h1>
            <p className="spc-cover-sub">
              <span>Weekly game</span>
              <span aria-hidden="true">·</span>
              <span className="spc-nowrap">
                <Lock size={12} aria-hidden="true" /> Private answers
              </span>
              <span aria-hidden="true">·</span>
              <span>Anonymous matching</span>
            </p>
            {fixture && (
              <span className="spc-mode" data-testid="cst-mode">
                Fixture mode · no server, no Muse
              </span>
            )}
          </div>
          {week.streak > 0 && (
            <span className="spc-streak-chip" title="Days in a row answered on the day">
              <Flame size={16} aria-hidden="true" /> {week.streak}-day streak
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
              cycleId={cycleId}
              go={go}
              onPost={onPost}
              busy={busy}
              error={error}
              onTook={setTook}
            />
          )}

          <WeekList week={week} question={question} go={go} />

          {week.day === 6 && (
            <section className="spc-card spc-today" data-testid="spc-weekend-sat">
              <div className="spc-post-head">
                <SpaceAvatar />
                <div>
                  <div className="spc-post-name is-big">Your week is in the sky</div>
                  <div className="spc-post-meta">Answers are locked. Your people are found Sunday at 10 AM.</div>
                </div>
              </div>
              <button type="button" className="spc-btn spc-btn-primary" onClick={() => go("sky")}>
                View sky
              </button>
            </section>
          )}
          {week.day === 7 && (
            <>
              <section className="spc-card spc-today" data-testid="spc-weekend-sun">
                <div className="spc-post-head">
                  <SpaceAvatar />
                  <div>
                    <div className="spc-post-name is-big">Your constellation is ready</div>
                    <div className="spc-post-meta">Meet the people who answered like you.</div>
                  </div>
                </div>
                <button type="button" className="spc-btn spc-btn-primary" onClick={() => go("main")}>
                  View constellation
                </button>
              </section>
              {(chatOn || eventsOn) && (
                <section className="spc-card spc-list">
                  {chatOn && (
                    <button type="button" className="spc-list-row" onClick={() => go("chat")}>
                      <span className="spc-list-icon is-tint" aria-hidden="true">
                        <MessageCircle size={20} />
                      </span>
                      <span className="spc-list-main">
                        Chat
                        <small>23 h left · Preview</small>
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
                          <small>{PREVIEW_INVITE.title}</small>
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
            <section className="spc-card spc-empty" data-testid="spc-weekend-over">
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
          {week.day <= 5 && <StatsCard day={statsDay} answered={answeredToday} count={count} took={took} />}
          <AboutCard />
          {demo}
        </aside>
      </div>
    </div>
  );
}
