/*
 * Constellations on the home feed, right under "What's on your mind?".
 * Not joined: one card with a Join button (consent opens in a dialog, no page change).
 * Joined: today's question with a private comment box, streak and catch-up count.
 */
import { useState } from "react";
import { Link } from "react-router";
import { ChevronRight, Flame, Lock, MoonStar } from "lucide-react";
import Modal from "../../../components/common/Modal";
import { allOn, getPrivacyClient, JoinScreen, usePrivacySession } from "../privacy";
import type { CycleClient } from "./client";
import { getCycleClient } from "./clientContext";
import { CONSTELLATIONS_PATH, JOIN_SCOPE_LABEL, PLAY_COMMUNITY } from "./communities";
import ConstellationsMark from "./ConstellationsMark";
import QuestionPost from "./QuestionPost";
import { DAY_NAMES, useDaily, when } from "./useDaily";
import WeekGraph from "./WeekGraph";
import "./daily.css";

const COMMUNITY = PLAY_COMMUNITY;
const PAGE = CONSTELLATIONS_PATH;

function Header({ streak, meta }: { streak: number | null; meta: string }) {
  return (
    <header className="cst-post-head">
      <ConstellationsMark />
      <div className="cst-post-who">
        <Link to={PAGE} className="cst-post-title">
          Constellations
        </Link>
        <span className="post-meta">
          {meta} <span aria-hidden="true">·</span> <Lock size={12} aria-label="Private answers" />
        </span>
      </div>
      {streak !== null && (
        <span className="cst-streak" data-testid="cst-feed-streak" title="Days in a row answered on the day">
          <Flame size={14} aria-hidden="true" /> {streak}
        </span>
      )}
    </header>
  );
}

function JoinedCard({ client }: { client: CycleClient }) {
  const { data, error, refresh } = useDaily(client);
  if (error)
    return (
      <section className="card cst-feed" aria-label="Constellations" data-testid="cst-feed-card">
        <Header streak={null} meta="Weekly game" />
        <p className="cst-error cst-pad" role="alert">
          {error}
        </p>
      </section>
    );
  if (!data) return <section className="card cst-feed cst-feed-loading" aria-label="Constellations" data-testid="cst-feed-card" aria-busy="true" />;

  const current = data.current;
  if (!current)
    return (
      <section className="card cst-feed" aria-label="Constellations" data-testid="cst-feed-card">
        <Header streak={null} meta="Weekly game" />
        <p className="cst-pad muted">No week is running yet. The first question arrives Monday morning.</p>
      </section>
    );

  const { cycle, streak, catchUp, question } = current;
  const open = cycle.status === "open" && question;
  return (
    <section className="card cst-feed" aria-label="Constellations" data-testid="cst-feed-card">
      <Header
        streak={streak.current}
        meta={open ? `${DAY_NAMES[cycle.currentDay - 1]}'s question` : cycle.status === "revealed" ? "Revealed" : "Locked"}
      />
      {open ? (
        <div className="cst-feed-question">
          <QuestionPost
            backdrop={<WeekGraph cycle={cycle} answers={data.answers} variant="dark" />}
            key={`${cycle.cycleId}-${question.day}`}
            client={client}
            cycleId={cycle.cycleId}
            item={question}
            answer={data.answers.find((a) => a.day === question.day)}
            kind="today"
            framed={false}
            onChanged={() => void refresh()}
          />
        </div>
      ) : (
        <div className="cst-feed-status">
          <span className="cst-icon-circle" aria-hidden="true">
            {cycle.status === "revealed" ? <MoonStar size={18} /> : <Lock size={18} />}
          </span>
          <p>
            {cycle.status === "revealed"
              ? "Your constellation is out. Meet them anonymously."
              : `Answers are locked. Constellations are revealed ${when(cycle.revealsAt)}.`}
          </p>
        </div>
      )}
      <Link to={PAGE} className="cst-feed-footer">
        <span>
          {catchUp.missedDays.length > 0
            ? `${catchUp.missedDays.length} missed ${catchUp.missedDays.length === 1 ? "day" : "days"} to catch up`
            : "See your week"}
        </span>
        <ChevronRight size={18} aria-hidden="true" />
      </Link>
    </section>
  );
}

export default function ConstellationsFeedCard() {
  const privacy = getPrivacyClient();
  const client = getCycleClient(COMMUNITY);
  const { state, set } = usePrivacySession(privacy, COMMUNITY);
  const [joining, setJoining] = useState(false);

  if (state.status === "loading") return <section className="card cst-feed cst-feed-loading" aria-label="Constellations" data-testid="cst-feed-card" aria-busy="true" />;

  if (state.status === "ready" && allOn(state.view.consent)) return <JoinedCard client={client} />;

  const paused = state.status === "ready";
  return (
    <section className="card cst-feed" aria-label="Constellations" data-testid="cst-feed-card">
      <Header streak={null} meta="Weekly game" />
      <div className="cst-feed-promo">
        <div className="cst-bg-post">
        <div className="cst-bg-backdrop" aria-hidden="true">
          <svg viewBox="0 0 600 220" className="cst-graph cst-graph-dark">
            <g className="cst-edges">
              <line className="cst-edge is-spoke-on" x1="300" y1="110" x2="170" y2="70" />
              <line className="cst-edge is-spoke-on" x1="300" y1="110" x2="230" y2="175" />
              <line className="cst-edge is-spoke" x1="300" y1="110" x2="370" y2="45" />
              <line className="cst-edge is-spoke" x1="300" y1="110" x2="430" y2="150" />
              <line className="cst-edge is-streak" x1="170" y1="70" x2="230" y2="175" />
              <line className="cst-edge is-chain" x1="370" y1="45" x2="430" y2="150" />
            </g>
            {[
              [300, 110, 14],
              [170, 70, 9],
              [230, 175, 9],
              [370, 45, 7],
              [430, 150, 7],
            ].map(([x, y, r]) => (
              <circle key={`${x}-${y}`} cx={x} cy={y} r={r} className="cst-promo-node" />
            ))}
          </svg>
        </div>
          <h2>One question a day. On Sunday, meet the 3–5 people whose week felt like yours.</h2>
        </div>
      </div>
      <div className="cst-feed-actions">
        <p className="muted">
          {paused ? "You paused Constellations. Turn it back on any time." : "Answers stay private. Matching is anonymous until you both choose to reveal."}
        </p>
        {paused ? (
          <Link to={PAGE} className="button-primary">
            Manage
          </Link>
        ) : (
          <button type="button" className="button-primary" onClick={() => setJoining(true)}>
            Join this week
          </button>
        )}
      </div>
      {joining && (
        <Modal title="Join Constellations" onClose={() => setJoining(false)} className="cst-join-modal">
          <JoinScreen
            client={privacy}
            communityId={COMMUNITY}
            communityName={JOIN_SCOPE_LABEL}
            onJoined={(view) => {
              setJoining(false);
              set(view);
            }}
          />
        </Modal>
      )}
    </section>
  );
}
