/*
 * Facebook Space on the home feed (V4 design), right under "What's on your mind?".
 * Joined + open: today's question on a night-sky block with a private composer.
 * Answer it like a comment; your answer then shows as your own private comment with your streak.
 * Not joined: the same card; sending opens Join in Space. "Open Space" is the one way into the tab.
 */
import { useState } from "react";
import { Link, useNavigate } from "react-router";
import { ArrowUp, Flame, Lock } from "lucide-react";
import Avatar from "../../../components/common/Avatar";
import { currentUser } from "../../../data/demo";
import { getPrivacyClient, usePrivacySession } from "../privacy";
import type { CycleClient } from "./client";
import { getCycleClient } from "./clientContext";
import { CONSTELLATIONS_PATH, FEATURE_NAME, PLAY_COMMUNITY } from "./communities";
import { DAY_LONG } from "./space/model";
import { MicIcon, SpaceAvatar, StarField } from "./space/parts";
import { useAnsweredToday } from "./space/stats";
import { useVoiceInput } from "./space/useVoiceInput";
import { MAX_CHARS, message, useDaily } from "./useDaily";
import "./space/space.css";

const COMMUNITY = PLAY_COMMUNITY;
const PAGE = CONSTELLATIONS_PATH;
const SCOPE = { scope: true };

function Card({ client, joined }: { client: CycleClient; joined: boolean }) {
  const { data, refresh } = useDaily(client);
  const navigate = useNavigate();
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const voice = useVoiceInput(client, setDraft);

  const current = data?.current ?? null;
  const cycle = current?.cycle;
  const open = cycle?.status === "open" && current?.question ? current.question : null;
  const answer = open && data ? data.answers.find((a) => a.day === open.day) : undefined;
  const answered = joined && Boolean(answer);

  const count = useAnsweredToday(client, cycle?.cycleId ?? null, answered && open ? open.day : null, answer?.answerId ?? null);
  const streak = joined ? (current?.streak.current ?? 0) : 0;

  const send = async () => {
    const text = draft.trim();
    if (!text || busy) return;
    if (!joined || !cycle || !open) return navigate(`${PAGE}`, { state: SCOPE });
    setBusy(true);
    setError(null);
    try {
      const result = await client.submit(cycle.cycleId, { day: open.day, text, source: voice.source });
      setDraft("");
      voice.reset();
      await refresh();
      if (result.supportCard) navigate(`${PAGE}?s=distress`);
    } catch (err) {
      setError(message(err));
    } finally {
      setBusy(false);
    }
  };

  const status = cycle?.status;
  const meta = open
    ? `${DAY_LONG[open.day - 1]}'s question · Private`
    : status === "revealed"
      ? "Your constellation is ready"
      : status === "locked" || status === "forming"
        ? "Locked until Sunday"
        : "Weekly game · Private";
  const headline = open
    ? open.question.text
    : status === "revealed"
      ? "Meet the people who answered like you."
      : status === "locked" || status === "forming"
        ? "Your week is in the sky."
        : "One easy question a day. On Sunday, meet the 3–5 people who answered like you.";

  return (
    <section className="card spc-feed" aria-label={FEATURE_NAME} data-testid="cst-feed-card">
      <div className="spc-feed-head">
        <SpaceAvatar />
        <div className="spc-grow">
          <Link to={PAGE} state={SCOPE} className="spc-feed-name">
            {FEATURE_NAME}
          </Link>
          <div className="spc-post-meta">{meta}</div>
        </div>
        <Link to={PAGE} state={SCOPE} className="spc-btn spc-btn-tint spc-btn-sm spc-pill-btn">
          {joined ? "Open Space" : "Join"}
        </Link>
      </div>
      <div className="spc-feed-sky">
        <StarField />
        <p className="spc-feed-q">{headline}</p>
      </div>
      {(streak > 0 || (answered && count !== null)) && (
        <div className="spc-feed-stats">
          {streak > 0 ? (
            <span className="spc-feed-streak" data-testid="cst-feed-streak">
              <Flame size={15} aria-hidden="true" /> {streak}-day streak
            </span>
          ) : (
            <span />
          )}
          {answered && count !== null && <span>{count.toLocaleString()} answered today</span>}
        </div>
      )}
      {open && !answered && (
        <div className="spc-feed-compose">
          <div className="spc-comment">
            <Avatar person={currentUser} size={32} />
            <div className="spc-comment-box">
              <textarea
                aria-label="Your answer"
                rows={1}
                value={draft}
                maxLength={MAX_CHARS}
                onChange={(e) => {
                  setDraft(e.target.value.slice(0, MAX_CHARS));
                  e.target.style.height = "auto";
                  e.target.style.height = `${e.target.scrollHeight}px`;
                }}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    void send();
                  }
                }}
                placeholder={voice.recording ? "Listening…" : joined ? "Answer privately…" : "Join to answer…"}
              />
              <div className="spc-comment-tools">
                <button
                  type="button"
                  className={`spc-comment-icon${voice.recording ? " is-on" : ""}`}
                  onClick={voice.toggle}
                  disabled={voice.blocked || !joined}
                  aria-label={voice.recording ? "Stop recording" : "Answer by voice"}
                  aria-pressed={voice.recording}
                >
                  <MicIcon />
                </button>
                <button type="button" className="spc-comment-icon is-send" disabled={!draft.trim() || busy} onClick={() => void send()} aria-label={joined ? "Send" : "Join to send"}>
                  <ArrowUp size={18} />
                </button>
              </div>
            </div>
          </div>
          <p className="spc-comment-note" aria-live="polite">
            <Lock size={11} aria-hidden="true" /> {voice.recording || voice.hint !== "or just talk" ? voice.hint : "Only you can see your answer"}
          </p>
          {error && (
            <p className="spc-error" role="alert">
              {error}
            </p>
          )}
        </div>
      )}
      {answered && open && answer && (
        <div className="spc-feed-compose">
          <div className="spc-comment">
            <Avatar person={currentUser} size={32} />
            <div>
              <div className="spc-comment-bubble">
                <b>{currentUser.name}</b>
                <span>{answer.text}</span>
              </div>
              <div className="spc-comment-meta">
                <Lock size={11} aria-hidden="true" /> Only you
                <span aria-hidden="true">·</span>
                <Link to={`${PAGE}?s=answer&day=${open.day}`}>Edit</Link>
              </div>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}

export default function ConstellationsFeedCard() {
  const privacy = getPrivacyClient();
  const client = getCycleClient(COMMUNITY);
  const { state } = usePrivacySession(privacy, COMMUNITY);
  if (state.status === "loading") return <section className="card spc-feed spc-feed-loading" aria-label={FEATURE_NAME} data-testid="cst-feed-card" aria-busy="true" />;
  return <Card client={client} joined={state.status === "ready"} />;
}
