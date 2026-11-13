import { useState } from "react";
import { Link } from "react-router";
import { Flame, Lock, MessageCircle, MoonStar, Settings2, Sparkles, Users } from "lucide-react";
import LeftSidebar from "../../../components/layout/LeftSidebar";
import { currentUser } from "../../../data/demo";
import { getPrivacyClient, PrivacyGate } from "../privacy";
import type { CycleClient, CycleDay, WeeklyCycle } from "./client";
import { getCycleClient } from "./clientContext";
import { FEATURE_NAME, JOIN_SCOPE_LABEL, OPERATOR_PATH, PLAY_COMMUNITY } from "./communities";
import ConstellationPreview from "./ConstellationPreview";
import ConstellationsMark from "./ConstellationsMark";
import EventHeat from "./EventHeat";
import GuessCard from "./GuessCard";
import MatchReasons from "./MatchReasons";
import QuestionPost from "./QuestionPost";
import StreakRewards from "./StreakRewards";
import { DAY_NAMES, useDaily, when } from "./useDaily";
import WeekGraph from "./WeekGraph";
import "./daily.css";

function weekOf(isoDate: string): string {
  return new Date(`${isoDate}T12:00:00Z`).toLocaleDateString(undefined, { month: "long", day: "numeric" });
}

function headline(cycle: WeeklyCycle): string {
  switch (cycle.status) {
    case "open":
      return `${DAY_NAMES[cycle.currentDay - 1]}'s question is open`;
    case "locked":
    case "forming":
      return "Locked until Sunday's reveal";
    case "revealed":
      return "Your constellation is out";
    default:
      return "This week has ended";
  }
}

function openDay(day: number) {
  const target = document.getElementById(`cst-day-${day}`);
  if (!target) return;
  const details = target.closest("details");
  if (details) details.open = true;
  target.scrollIntoView({ behavior: "smooth", block: "center" });
  target.querySelector<HTMLTextAreaElement>("textarea")?.focus({ preventScroll: true });
}

function DailyContent({ client, tab }: { client: CycleClient; tab: "week" | "constellation" }) {
  const { data, error, refresh } = useDaily(client);

  if (error)
    return (
      <section className="card cst-panel">
        <p className="cst-error" role="alert">
          {error}
        </p>
        <div className="cst-panel-foot">
          <button type="button" className="button-secondary" onClick={() => void refresh()}>
            Try again
          </button>
        </div>
      </section>
    );

  if (!data)
    return (
      <div className="cst-skeleton" role="status" aria-live="polite">
        <span className="sr-only">Loading this week…</span>
        <div className="card cst-skel cst-skel-graph" />
        <div className="card cst-skel cst-skel-post" />
      </div>
    );

  const current = data.current;
  if (!current)
    return (
      <section className="card cst-empty">
        <span className="cst-icon-circle is-large" aria-hidden="true">
          <MoonStar size={26} />
        </span>
        <h2>No week is running yet</h2>
        <p className="muted">The next week opens Monday morning with its first question.</p>
      </section>
    );

  const { cycle, catchUp, streak } = current;
  if (tab === "constellation")
    return (
      <>
        <ConstellationPreview revealsAt={cycle.status === "open" || cycle.status === "locked" || cycle.status === "forming" ? cycle.revealsAt : null} />
        <MatchReasons />
        <EventHeat />
      </>
    );
  const answerFor = (day: number) => data.answers.find((a) => a.day === day);
  const questionFor = (day: number) => data.questions.find((q) => q.day === day as CycleDay);
  const past = cycle.status === "open" ? [1, 2, 3, 4, 5].filter((day) => day < cycle.currentDay) : [];
  const catchUpDays = past.filter((day) => !answerFor(day) || answerFor(day)!.isCatchUp);
  const earlierDays = past.filter((day) => answerFor(day) && !answerFor(day)!.isCatchUp);
  const post = (day: number, kind: "today" | "catch-up" | "earlier") => {
    const item = questionFor(day);
    return item ? (
      <QuestionPost
        key={`${cycle.cycleId}-${kind}-${day}`}
        client={client}
        cycleId={cycle.cycleId}
        item={item}
        answer={answerFor(day)}
        kind={kind}
        onChanged={() => void refresh()}
      />
    ) : null;
  };

  return (
    <>
      <section className="card cst-panel cst-week" aria-labelledby="cst-week-title">
        <header className="cst-panel-head">
          <div>
            <h2 id="cst-week-title">Your week</h2>
            <p className="muted">
              Week of {weekOf(cycle.weekStart)} · {headline(cycle)}
            </p>
          </div>
          <span className="cst-streak" data-testid="cst-streak" title="Question days in a row answered on the day">
            <Flame size={15} aria-hidden="true" /> Streak {streak.current}
          </span>
        </header>
        <div className="cst-graph-wrap">
          <WeekGraph cycle={cycle} answers={data.answers} avatar={currentUser.avatar} onSelectDay={openDay} />
          <p className="cst-graph-caption">Your days this week. Tap a day to answer it.</p>
        </div>
        <div className="cst-legend" aria-hidden="true">
          <span>
            <i className="is-answered" /> Answered
          </span>
          <span>
            <i className="is-caught-up" /> Caught up
          </span>
          <span>
            <i className="is-today" /> Today
          </span>
          <span>
            <i className="is-missed" /> Missed
          </span>
          <span>
            <i className="is-streak" /> Streak
          </span>
        </div>
        {cycle.demoTiming && (
          <p className="cst-panel-note">
            <span className="cst-label cst-label-warn">Demo timing</span> Days move when the operator advances them.
          </p>
        )}
      </section>

      {cycle.status === "open" ? (
        <>
          {current.question && post(current.question.day, "today")}

          {catchUpDays.length > 0 && (
            <section className="cst-group" aria-labelledby="cst-catchup-title">
              <div className="cst-group-head">
                <h2 id="cst-catchup-title">Catch up</h2>
                {catchUp.missedDays.length > 0 && (
                  <p className="muted" data-testid="cst-catchup-note">
                    {catchUp.missedDays.length} missed {catchUp.missedDays.length === 1 ? "day" : "days"} to catch up.
                    Closes {when(catchUp.closesAt)}.
                  </p>
                )}
              </div>
              {catchUpDays.map((day) => post(day, "catch-up"))}
            </section>
          )}

          <StreakRewards streak={streak} answers={data.answers} />

          <GuessCard key={cycle.cycleId} client={client} cycleId={cycle.cycleId} saved={data.guess} />

          {earlierDays.length > 0 && (
            <details className="cst-earlier">
              <summary className="card">
                Earlier this week · {earlierDays.length} {earlierDays.length === 1 ? "answer" : "answers"}
              </summary>
              {earlierDays.map((day) => post(day, "earlier"))}
            </details>
          )}
        </>
      ) : (
        <section className="card cst-empty" data-testid="cst-locked">
          <span className="cst-icon-circle is-large" aria-hidden="true">
            {cycle.status === "revealed" ? <MoonStar size={26} /> : <Lock size={24} />}
          </span>
          <h2>
            {cycle.status === "locked" || cycle.status === "forming"
              ? "This week is locked"
              : cycle.status === "revealed"
                ? "Your constellation is out"
                : "This week has ended"}
          </h2>
          <p className="muted">
            {cycle.status === "locked" || cycle.status === "forming"
              ? `You answered ${data.answers.length} of 5. Your constellation is revealed ${when(cycle.revealsAt)}.`
              : cycle.status === "revealed"
                ? `You answered ${data.answers.length} of 5. Your anonymous chat stays open until ${when(cycle.chatExpiresAt)}.`
                : "Thanks for playing. A new week opens Monday morning."}
          </p>
        </section>
      )}
      {cycle.status !== "open" && <StreakRewards streak={streak} answers={data.answers} />}
    </>
  );
}

function About({ operator }: { operator: boolean }) {
  return (
    <aside className="cst-side" aria-label={`About ${FEATURE_NAME}`}>
      <section className="card cst-panel">
        <h2 className="cst-side-title">About</h2>
        <ol className="cst-steps-list">
          <li>
            <span className="cst-icon-circle" aria-hidden="true">
              <Sparkles size={16} />
            </span>
            <div>
              <strong>Mon–Fri: one easy question a day</strong>
              <p className="muted">About a minute, by typing or voice. Missed a day? Catch up until Saturday noon. It all resets Monday.</p>
            </div>
          </li>
          <li>
            <span className="cst-icon-circle" aria-hidden="true">
              <Users size={16} />
            </span>
            <div>
              <strong>Sunday: meet your constellation</strong>
              <p className="muted">
                The 3 to 5 people whose answers meant the most similar things. The closer the match, the brighter their
                star. No first move needed: the group is made for you.
              </p>
            </div>
          </li>
          <li>
            <span className="cst-icon-circle" aria-hidden="true">
              <MessageCircle size={16} />
            </span>
            <div>
              <strong>Anonymous chat, all week</strong>
              <p className="muted">You're a Star handle. Names appear only if you both choose to reveal, and then you can add each other as friends.</p>
            </div>
          </li>
        </ol>
      </section>
      <section className="card cst-panel">
        <h2 className="cst-side-title">Privacy</h2>
        <p className="muted">
          <Lock size={13} aria-hidden="true" /> Nobody ever reads your answers. Patterns across players appear only when 3 or more people share them.
        </p>
      </section>
      {operator && (
        <Link className="card cst-side-link" to={OPERATOR_PATH}>
          <span className="cst-icon-circle" aria-hidden="true">
            <Settings2 size={16} />
          </span>
          <span>
            <strong>Operator console</strong>
            <small className="muted">Run the demo week</small>
          </span>
        </Link>
      )}
    </aside>
  );
}

export default function DailyPage() {
  const communityId = PLAY_COMMUNITY;
  const client = getCycleClient(communityId);
  const [epoch, setEpoch] = useState(0);
  const [tab, setTab] = useState<"week" | "constellation">("week");

  return (
    <div className="secondary-layout cst-layout">
      <LeftSidebar />
      <main className="cst-page" id="main-content">
        <header className="card cst-group-header">
          <div className="cst-cover" aria-hidden="true">
            <svg viewBox="0 0 800 200" preserveAspectRatio="xMidYMid slice">
              <g className="cst-cover-lines">
                <line x1="140" y1="120" x2="230" y2="70" />
                <line x1="230" y1="70" x2="330" y2="110" />
                <line x1="330" y1="110" x2="300" y2="160" />
                <line x1="520" y1="60" x2="610" y2="100" />
                <line x1="610" y1="100" x2="690" y2="50" />
                <line x1="610" y1="100" x2="640" y2="150" />
              </g>
              <g className="cst-cover-stars">
                {[[140, 120, 3], [230, 70, 4], [330, 110, 3], [300, 160, 2.5], [520, 60, 3], [610, 100, 4.5], [690, 50, 3], [640, 150, 2.5], [60, 40, 1.5], [420, 30, 1.5], [460, 170, 1.5], [760, 140, 1.5], [90, 170, 1.2], [380, 60, 1.2]].map(([x, y, r]) => (
                  <circle key={`${x}-${y}`} cx={x} cy={y} r={r} />
                ))}
              </g>
            </svg>
          </div>
          <div className="cst-group-id">
            <div className="cst-title-row">
              <ConstellationsMark size={56} />
              <div>
                <h1>{FEATURE_NAME}</h1>
                <p className="muted">A weekly game across Facebook · Private answers · Anonymous matching</p>
              </div>
            </div>
            <p className="cst-labels">
              <span className="cst-label">Simulated Facebook</span>
              {client.mode === "fixture" && (
                <span className="cst-label cst-label-warn" data-testid="cst-mode">
                  Fixture mode · no server, no Muse
                </span>
              )}
            </p>
          </div>
          <div className="cst-tabs" role="tablist" aria-label={`${FEATURE_NAME} sections`}>
            <button
              type="button"
              role="tab"
              id="cst-tab-week"
              aria-selected={tab === "week"}
              aria-controls="cst-tabpanel"
              className={`cst-tab${tab === "week" ? " is-active" : ""}`}
              onClick={() => setTab("week")}
            >
              This week
            </button>
            <button
              type="button"
              role="tab"
              id="cst-tab-constellation"
              aria-selected={tab === "constellation"}
              aria-controls="cst-tabpanel"
              className={`cst-tab${tab === "constellation" ? " is-active" : ""}`}
              onClick={() => setTab("constellation")}
            >
              Constellation <small>Sun</small>
            </button>
          </div>
        </header>

        <div className="cst-columns">
          <div className="cst-main" role="tabpanel" id="cst-tabpanel" aria-labelledby={tab === "week" ? "cst-tab-week" : "cst-tab-constellation"}>
            <PrivacyGate
              client={getPrivacyClient()}
              communityId={communityId}
              communityName={JOIN_SCOPE_LABEL}
              onDataDeleted={() => {
                client.clearLocalData?.(); // fixture only; the server deletes in live mode
                setEpoch((value) => value + 1);
              }}
            >
              <DailyContent key={epoch} client={client} tab={tab} />
            </PrivacyGate>
          </div>
          <About operator={client.isOperator} />
        </div>

        <p className="secondary-prototype-note">Unofficial hackathon prototype · Fictional demo content</p>
      </main>
    </div>
  );
}
