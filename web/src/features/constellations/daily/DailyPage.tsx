import { useCallback, useEffect, useRef, useState, type CSSProperties } from "react";
import { Link, useParams } from "react-router";
import { Check, Clock, Flame, Lock, Mic, MoonStar, Pencil, Sparkles, Square, Trash2 } from "lucide-react";
import { getPrivacyClient, PrivacyGate, SupportCard } from "../privacy";
import {
  ClientError,
  type CurrentCycle,
  type CycleClient,
  type CycleDay,
  type DailyAnswer,
  type DailyQuestion,
  type FollowUp,
  type WeeklyCycle,
} from "./client";
import { getCycleClient } from "./clientContext";
import { COMMUNITIES } from "./communities";
import { MAX_RECORDING_SECONDS, useVoiceRecorder } from "./useVoiceRecorder";
import "./daily.css";

const DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"];
const MAX_CHARS = 400;

function message(error: unknown): string {
  if (error instanceof ClientError) {
    if (error.code === "CYCLE_LOCKED") return "This week is locked. Answers can no longer change.";
    if (error.code === "UNAUTHENTICATED") return "Join the group's Constellations game to answer.";
    if (error.code === "CONSENT_REQUIRED") return "Turn on all three consents to keep playing.";
    return error.message;
  }
  return "Something went wrong. Try again.";
}

function when(iso: string): string {
  return new Date(iso).toLocaleString(undefined, { weekday: "long", hour: "numeric", minute: "2-digit" });
}

function weekOf(isoDate: string): string {
  return new Date(`${isoDate}T12:00:00Z`).toLocaleDateString(undefined, { month: "long", day: "numeric" });
}

function clock(seconds: number): string {
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;
}

interface Loaded {
  current: CurrentCycle | null;
  questions: DailyQuestion[];
  answers: DailyAnswer[];
  guess: number | null;
}

function useDaily(client: CycleClient) {
  const [data, setData] = useState<Loaded | null>(null);
  const [error, setError] = useState<string | null>(null);
  const request = useRef(0);

  const refresh = useCallback(async () => {
    const id = ++request.current;
    try {
      const current = await client.current();
      const [questions, answers, guess] = current
        ? await Promise.all([
            client.questions(current.cycle.cycleId),
            client.myAnswers(current.cycle.cycleId),
            client.myGuess(current.cycle.cycleId),
          ])
        : [[], [], null];
      if (id !== request.current) return; // a newer refresh superseded this one
      setData({ current, questions, answers, guess });
      setError(null);
    } catch (err) {
      if (id !== request.current) return;
      setError(message(err));
    }
  }, [client]);

  useEffect(() => {
    const counter = request;
    void refresh();
    const unsubscribe = client.subscribe(() => void refresh());
    return () => {
      counter.current++;
      unsubscribe();
    };
  }, [client, refresh]);

  return { data, error, refresh };
}

// ---- week constellation ---------------------------------------------------------
type DayState = "answered" | "caught-up" | "today" | "missed" | "upcoming";
const DAY_LABEL: Record<DayState, string> = {
  answered: "Answered",
  "caught-up": "Caught up",
  today: "Today",
  missed: "Missed",
  upcoming: "Upcoming",
};
// Star positions: one per column of the week grid (x centers at 30, 90, ... 270).
const STARS: [number, number][] = [
  [30, 52],
  [90, 26],
  [150, 46],
  [210, 18],
  [270, 38],
];

function dayStates(cycle: WeeklyCycle, answers: DailyAnswer[]): DayState[] {
  const open = cycle.status === "open";
  return [1, 2, 3, 4, 5].map((day) => {
    const answer = answers.find((a) => a.day === day);
    if (answer) return answer.isCatchUp ? "caught-up" : "answered";
    if (open && day === cycle.currentDay) return "today";
    if (open && day > cycle.currentDay) return "upcoming";
    return "missed";
  });
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

function WeekSky({ current, answers }: { current: CurrentCycle; answers: DailyAnswer[] }) {
  const { cycle, streak } = current;
  const states = dayStates(cycle, answers);
  const answered = (s: DayState) => s === "answered" || s === "caught-up";
  return (
    <section className="cst-sky" aria-label="Your week">
      <div className="cst-sky-top">
        <div>
          <p className="cst-sky-kicker">Week of {weekOf(cycle.weekStart)}</p>
          <p className="cst-sky-title">{headline(cycle)}</p>
        </div>
        <span
          className="cst-streak"
          data-testid="cst-streak"
          title="Question days in a row answered on the day. Catch-up days don't add to it."
        >
          <Flame size={15} aria-hidden="true" />
          Streak {streak.current}
        </span>
      </div>

      <svg className="cst-sky-svg" viewBox="0 0 300 70" aria-hidden="true" focusable="false">
        {STARS.slice(0, 4).map(([x, y], i) => {
          const [nx, ny] = STARS[i + 1];
          const a = states[i];
          const b = states[i + 1];
          if (a === "answered" && b === "answered")
            return <line key={i} x1={x} y1={y} x2={nx} y2={ny} className="cst-link cst-link-streak" />;
          if (answered(a) && answered(b))
            return <line key={i} x1={x} y1={y} x2={nx} y2={ny} className="cst-link cst-link-soft" />;
          return null;
        })}
        {STARS.map(([x, y], i) => {
          const state = states[i];
          return (
            <g key={i} className={`cst-star cst-star-${state}`}>
              {state === "answered" && <circle cx={x} cy={y} r={13} className="cst-star-glow" />}
              {state === "today" && <circle cx={x} cy={y} r={10} className="cst-star-ring" />}
              <circle
                cx={x}
                cy={y}
                r={state === "answered" ? 5.5 : state === "upcoming" ? 2.5 : state === "missed" ? 3.5 : 4.5}
                className="cst-star-core"
              />
            </g>
          );
        })}
      </svg>

      <ol className="cst-week" aria-label="This week">
        {DAY_NAMES.map((name, index) => (
          <li key={name} className={`cst-day is-${states[index]}`}>
            <span className="cst-day-name" aria-hidden="true">
              {name.slice(0, 3)}
            </span>
            <span className="cst-day-state">
              <span className="cst-sr">{name}: </span>
              {DAY_LABEL[states[index]]}
            </span>
          </li>
        ))}
      </ol>

      {cycle.demoTiming && (
        <p className="cst-sky-foot">
          <span className="cst-chip cst-chip-sky">Demo timing</span>
          <span>Days move when the operator advances them.</span>
        </p>
      )}
    </section>
  );
}

// ---- one question -------------------------------------------------------------
function AnswerCard({
  client,
  cycleId,
  item,
  answer,
  kind,
  onChanged,
}: {
  client: CycleClient;
  cycleId: string;
  item: DailyQuestion;
  answer: DailyAnswer | undefined;
  kind: "today" | "catch-up" | "earlier";
  onChanged: () => void;
}) {
  const [text, setText] = useState("");
  const [source, setSource] = useState<"voice" | "text">("text");
  const [editing, setEditing] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [voiceNote, setVoiceNote] = useState<string | null>(null);
  const [support, setSupport] = useState(false);
  const [followUp, setFollowUp] = useState<FollowUp | null>(null);
  const [reply, setReply] = useState("");
  const [skipped, setSkipped] = useState(false);
  const transcription = useRef<AbortController | null>(null);
  const field = useRef<HTMLTextAreaElement | null>(null);
  const day = item.day;
  const fieldId = `cst-answer-${day}`;

  const recorder = useVoiceRecorder(async (audio) => {
    transcription.current?.abort();
    const controller = new AbortController();
    transcription.current = controller;
    setVoiceNote("Transcribing…");
    try {
      const result = await client.transcribe(audio, controller.signal);
      if (controller.signal.aborted) return;
      setText(result.transcript.slice(0, MAX_CHARS));
      setSource("voice");
      setVoiceNote(
        result.mode === "fixture"
          ? "Fixture transcript, not your voice. Edit it before submitting."
          : "Check the transcript, edit if needed, then submit.",
      );
      field.current?.focus();
    } catch (err) {
      if (controller.signal.aborted) return;
      setVoiceNote(`${message(err)} You can type your answer instead.`);
    }
  });
  useEffect(() => () => transcription.current?.abort(), []);

  const recording = recorder.status === "recording";
  const micBlocked = recorder.status === "denied" || recorder.status === "unsupported";
  const micNote =
    recorder.status === "denied"
      ? "Microphone access is off. Typing works the same."
      : recorder.status === "unsupported"
        ? "This browser can't record. Typing works the same."
        : recorder.status === "error"
          ? `${recorder.error ?? "Recording failed."} You can type instead.`
          : recording
            ? "Recording. Tap stop when you're done."
            : voiceNote;

  async function run(work: () => Promise<void>) {
    setBusy(true);
    setError(null);
    try {
      await work();
    } catch (err) {
      setError(message(err));
    } finally {
      setBusy(false);
    }
  }

  const loadFollowUp = async () => {
    try {
      setFollowUp(await client.followUp(cycleId, day));
    } catch {
      setFollowUp(null); // the follow-up is optional; the answer is already saved
    }
  };

  const save = () =>
    run(async () => {
      const result = answer
        ? await client.edit(cycleId, day, { text })
        : await client.submit(cycleId, { day, text, source });
      setSupport(result.supportCard);
      setEditing(false);
      setText("");
      setVoiceNote(null);
      if (!answer && !result.supportCard) void loadFollowUp();
      onChanged();
    });

  const sendReply = () =>
    run(async () => {
      if (!answer) return;
      const combined = `${answer.text} ${reply}`.trim().slice(0, MAX_CHARS);
      const result = await client.edit(cycleId, day, { text: combined, answersFollowUp: true });
      setSupport(result.supportCard);
      setFollowUp(null);
      setReply("");
      onChanged();
    });

  const remove = () =>
    run(async () => {
      await client.remove(cycleId, day);
      setConfirmDelete(false);
      setSupport(false);
      setFollowUp(null);
      onChanged();
    });

  const showForm = !answer || editing;
  const trimmed = text.trim();
  const eyebrow = kind === "today" ? "Today" : kind === "earlier" ? "Earlier this week" : "Catch-up";

  return (
    <section
      className={`cst-card cst-qcard is-${kind}`}
      aria-labelledby={`cst-q-${day}`}
      data-testid={`cst-day-${day}`}
    >
      <p className="cst-eyebrow">
        {eyebrow} · {DAY_NAMES[day - 1]}
      </p>
      <h2 id={`cst-q-${day}`} className="cst-question">
        {item.question.text}
      </h2>
      {kind === "catch-up" && !answer && (
        <p className="cst-hint">Catch-up answers count at a lower weight and don't extend your streak.</p>
      )}

      {showForm ? (
        <form
          className="cst-composer"
          onSubmit={(event) => {
            event.preventDefault();
            if (trimmed && !busy && !recording) void save();
          }}
        >
          <label className="cst-sr" htmlFor={fieldId}>
            {answer ? "Edit your answer" : "Your answer"}
          </label>
          <div className={`cst-field${recording ? " is-recording" : ""}`}>
            <textarea
              id={fieldId}
              ref={field}
              className="cst-textarea"
              rows={4}
              maxLength={MAX_CHARS}
              value={text}
              placeholder={kind === "today" ? "Say it however it comes out." : "Your answer"}
              onChange={(event) => {
                setText(event.target.value);
                if (!event.target.value) setSource("text");
              }}
            />
            <div className="cst-field-bar">
              <span className="cst-private">
                <Lock size={12} aria-hidden="true" /> Only you can read this
              </span>
              <span className={`cst-count${text.length > MAX_CHARS - 40 ? " is-near" : ""}`}>
                {text.length}/{MAX_CHARS}
              </span>
            </div>
          </div>
          <p className="cst-voice-note" role="status">
            {micNote}
          </p>
          <div className="cst-actions">
            <button type="submit" className="button-primary cst-grow" disabled={!trimmed || busy || recording}>
              {busy ? "Saving…" : answer ? "Save changes" : "Submit answer"}
            </button>
            {recording ? (
              <button
                type="button"
                className="cst-mic is-live"
                onClick={recorder.stop}
                aria-label={`Stop recording, ${recorder.seconds} of ${MAX_RECORDING_SECONDS} seconds`}
              >
                <Square size={14} aria-hidden="true" fill="currentColor" />
                <span aria-hidden="true">{clock(recorder.seconds)}</span>
              </button>
            ) : (
              <button
                type="button"
                className="cst-mic"
                onClick={() => void recorder.start()}
                disabled={micBlocked || recorder.status === "requesting" || busy}
              >
                <Mic size={16} aria-hidden="true" />
                <span>Record answer</span>
              </button>
            )}
            {answer && (
              <button
                type="button"
                className="cst-text-button"
                onClick={() => {
                  setEditing(false);
                  setText("");
                }}
                disabled={busy}
              >
                Cancel
              </button>
            )}
          </div>
        </form>
      ) : (
        <div className="cst-saved">
          <p className="cst-answer" data-testid={`cst-answer-text-${day}`}>
            {answer.text}
          </p>
          <div className="cst-saved-bar">
            <p className="cst-meta">
              <Check size={14} aria-hidden="true" /> Saved{answer.isCatchUp ? " as catch-up" : ""} · private to you ·{" "}
              {answer.source === "voice" ? "from voice" : "typed"}
            </p>
            {confirmDelete ? (
              <div className="cst-confirm" role="group" aria-label="Confirm delete">
                <span>Delete this answer?</span>
                <button type="button" className="cst-danger" onClick={() => void remove()} disabled={busy}>
                  Delete answer
                </button>
                <button type="button" className="cst-text-button" onClick={() => setConfirmDelete(false)}>
                  Keep it
                </button>
              </div>
            ) : (
              <div className="cst-inline-actions">
                <button
                  type="button"
                  className="cst-text-button"
                  onClick={() => {
                    setText(answer.text);
                    setEditing(true);
                  }}
                  disabled={busy}
                >
                  <Pencil size={14} aria-hidden="true" /> Edit
                </button>
                <button
                  type="button"
                  className="cst-text-button"
                  onClick={() => setConfirmDelete(true)}
                  disabled={busy}
                >
                  <Trash2 size={14} aria-hidden="true" /> Delete
                </button>
              </div>
            )}
          </div>
        </div>
      )}

      {error && (
        <p className="cst-error" role="alert">
          {error}
        </p>
      )}

      {support && <SupportCard />}

      {answer && !editing && followUp?.needsFollowup && !answer.followUpUsed && !skipped && (
        <form
          className="cst-followup"
          onSubmit={(event) => {
            event.preventDefault();
            if (reply.trim() && !busy) void sendReply();
          }}
        >
          <p className="cst-chip cst-chip-muse" data-testid="cst-muse-chip">
            <Sparkles size={13} aria-hidden="true" />
            {client.mode === "fixture"
              ? "Fixture follow-up · not Muse"
              : followUp.evidence
                ? `Muse · ${followUp.evidence.model} · ${followUp.evidence.source === "replay" ? "Replay of a saved cycle" : "live"} · ${(followUp.evidence.latencyMs / 1000).toFixed(1)} s`
                : "Muse follow-up"}
          </p>
          <label className="cst-followup-q" htmlFor={`cst-reply-${day}`}>
            {followUp.question}
          </label>
          <textarea
            id={`cst-reply-${day}`}
            className="cst-textarea cst-textarea-small"
            rows={2}
            maxLength={Math.max(0, MAX_CHARS - answer.text.length - 1)}
            value={reply}
            onChange={(event) => setReply(event.target.value)}
          />
          <div className="cst-actions">
            <button type="submit" className="button-primary" disabled={!reply.trim() || busy}>
              Add to my answer
            </button>
            <button type="button" className="cst-text-button" onClick={() => setSkipped(true)}>
              Skip
            </button>
          </div>
          <p className="cst-hint">Optional. Adding a little more helps Muse find your people.</p>
        </form>
      )}
    </section>
  );
}

// ---- prevalence guess -------------------------------------------------------------
function GuessCard({ client, cycleId, saved }: { client: CycleClient; cycleId: string; saved: number | null }) {
  const [value, setValue] = useState(saved ?? 50);
  const [stored, setStored] = useState(saved);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function save() {
    setBusy(true);
    setError(null);
    try {
      setStored((await client.guess(cycleId, value)).percent);
    } catch (err) {
      setError(message(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="cst-card cst-guess" aria-labelledby="cst-guess-title">
      <p className="cst-eyebrow">Before Sunday</p>
      <h2 id="cst-guess-title" className="cst-question">
        How many people here feel like you this week?
      </h2>
      <p className="cst-hint">
        Private. On Sunday the Sky shows how the Group's guesses compare with what people really shared.
      </p>
      <p className="cst-guess-value" aria-hidden="true">
        {value}
        <span>%</span>
      </p>
      <label className="cst-sr" htmlFor="cst-guess">
        Your guess: {value}%
      </label>
      <input
        id="cst-guess"
        className="cst-slider"
        type="range"
        min={0}
        max={100}
        step={1}
        value={value}
        style={{ "--cst-fill": `${value}%` } as CSSProperties}
        onChange={(event) => setValue(Number(event.target.value))}
      />
      <div className="cst-scale" aria-hidden="true">
        <span>Just me</span>
        <span>About half</span>
        <span>Everyone</span>
      </div>
      <div className="cst-actions">
        <button
          type="button"
          className="button-primary"
          onClick={() => void save()}
          disabled={busy || stored === value}
        >
          {stored === null ? "Save guess" : stored === value ? "Guess saved" : "Update guess"}
        </button>
        {stored !== null && (
          <span className="cst-meta" role="status">
            <Check size={14} aria-hidden="true" /> Saved: {stored}%
          </span>
        )}
      </div>
      {error && (
        <p className="cst-error" role="alert">
          {error}
        </p>
      )}
    </section>
  );
}

// ---- after Friday ---------------------------------------------------------------
function WeekStatusCard({ cycle, answered }: { cycle: WeeklyCycle; answered: number }) {
  const locked = cycle.status === "locked" || cycle.status === "forming";
  return (
    <section className="cst-card cst-status-card" data-testid="cst-locked" aria-labelledby="cst-status-title">
      <span className="cst-status-icon" aria-hidden="true">
        {locked ? <Lock size={20} /> : <MoonStar size={20} />}
      </span>
      <h2 id="cst-status-title" className="cst-question">
        {locked ? "This week is locked" : cycle.status === "revealed" ? "Your constellation is out" : "This week has ended"}
      </h2>
      <p className="cst-hint">
        {locked
          ? `You answered ${answered} of 5. Answers are final, and Muse is finding the people whose week sounded like yours.`
          : cycle.status === "revealed"
            ? `You answered ${answered} of 5. Your constellation's anonymous chat stays open until the next lock.`
            : "Thanks for playing. A new week opens Monday morning."}
      </p>
      <dl className="cst-when">
        {locked && (
          <div>
            <dt>
              <Clock size={14} aria-hidden="true" /> Reveal
            </dt>
            <dd>{when(cycle.revealsAt)}</dd>
          </div>
        )}
        {cycle.status === "revealed" && (
          <div>
            <dt>
              <Clock size={14} aria-hidden="true" /> Chat closes
            </dt>
            <dd>{when(cycle.chatExpiresAt)}</dd>
          </div>
        )}
      </dl>
    </section>
  );
}

function Skeleton() {
  return (
    <div className="cst-skeleton" role="status" aria-live="polite">
      <span className="cst-sr">Loading this week…</span>
      <div className="cst-skel cst-skel-sky" />
      <div className="cst-skel cst-skel-card" />
    </div>
  );
}

// ---- page -----------------------------------------------------------------------
function DailyContent({ client }: { client: CycleClient }) {
  const { data, error, refresh } = useDaily(client);

  if (error)
    return (
      <section className="cst-card">
        <p className="cst-error" role="alert">
          {error}
        </p>
        <div className="cst-actions">
          <button type="button" className="button-secondary" onClick={() => void refresh()}>
            Try again
          </button>
        </div>
      </section>
    );

  if (!data) return <Skeleton />;

  const current = data.current;
  if (!current)
    return (
      <section className="cst-card cst-empty">
        <svg viewBox="0 0 120 48" className="cst-empty-art" aria-hidden="true" focusable="false">
          <line x1="14" y1="34" x2="46" y2="14" />
          <line x1="46" y1="14" x2="76" y2="28" />
          <line x1="76" y1="28" x2="106" y2="10" />
          <circle cx="14" cy="34" r="3" />
          <circle cx="46" cy="14" r="4" />
          <circle cx="76" cy="28" r="3" />
          <circle cx="106" cy="10" r="4" />
        </svg>
        <h2 className="cst-question">No week is running yet</h2>
        <p className="cst-hint">The next week opens Monday morning with its first question. Check back then.</p>
      </section>
    );

  const { cycle, catchUp } = current;
  const answerFor = (day: number) => data.answers.find((a) => a.day === day);
  const questionFor = (day: number) => data.questions.find((q) => q.day === day);
  const past = cycle.status === "open" ? [1, 2, 3, 4, 5].filter((day) => day < cycle.currentDay) : [];
  const catchUpDays = past.filter((day) => !answerFor(day) || answerFor(day)!.isCatchUp);
  const earlierDays = past.filter((day) => answerFor(day) && !answerFor(day)!.isCatchUp);
  const card = (day: number, kind: "today" | "catch-up" | "earlier") => {
    const item = questionFor(day as CycleDay);
    if (!item) return null;
    return (
      <AnswerCard
        key={`${cycle.cycleId}-${kind}-${day}`}
        client={client}
        cycleId={cycle.cycleId}
        item={item}
        answer={answerFor(day)}
        kind={kind}
        onChanged={() => void refresh()}
      />
    );
  };

  return (
    <>
      <WeekSky current={current} answers={data.answers} />

      {cycle.status === "open" ? (
        <>
          {current.question && card(current.question.day, "today")}

          {catchUpDays.length > 0 && (
            <section className="cst-section" aria-labelledby="cst-catchup-title">
              <div className="cst-section-head">
                <h2 id="cst-catchup-title">Catch up</h2>
                {catchUp.missedDays.length > 0 && (
                  <p className="cst-hint" data-testid="cst-catchup-note">
                    {catchUp.missedDays.length} missed {catchUp.missedDays.length === 1 ? "day" : "days"} to catch up.
                    Closes {when(catchUp.closesAt)}.
                  </p>
                )}
              </div>
              {catchUpDays.map((day) => card(day, "catch-up"))}
            </section>
          )}

          <GuessCard key={cycle.cycleId} client={client} cycleId={cycle.cycleId} saved={data.guess} />

          {earlierDays.length > 0 && (
            <details className="cst-earlier">
              <summary>
                Earlier this week · {earlierDays.length} {earlierDays.length === 1 ? "answer" : "answers"}
              </summary>
              {earlierDays.map((day) => card(day, "earlier"))}
            </details>
          )}
        </>
      ) : (
        <WeekStatusCard cycle={cycle} answered={data.answers.length} />
      )}
    </>
  );
}

export default function DailyPage() {
  const { communityId = "" } = useParams();
  const communityName = COMMUNITIES[communityId];
  const client = getCycleClient(communityId);
  const [epoch, setEpoch] = useState(0);

  if (!communityName) {
    return (
      <main className="cst-page" id="main-content">
        <section className="cst-card cst-empty">
          <h1 className="cst-question">Group not found</h1>
          <p className="cst-hint">This Group doesn't have Constellations, or the link is wrong.</p>
          <div className="cst-actions">
            <Link className="button-secondary" to="/groups">
              Back to Groups
            </Link>
          </div>
        </section>
      </main>
    );
  }

  return (
    <main className="cst-page" id="main-content">
      <header className="cst-header">
        <nav className="cst-breadcrumb" aria-label="Breadcrumb">
          <Link to="/groups">Groups</Link>
          <span aria-hidden="true">/</span>
          <span>{communityName}</span>
        </nav>
        <h1>Constellations</h1>
        <p className="cst-tagline">
          One question a day, Monday to Friday. On Sunday, meet the 3 to 5 people whose week sounded like yours.
        </p>
        <p className="cst-chips">
          <span className="cst-chip">Simulated Facebook</span>
          {client.mode === "fixture" && (
            <span className="cst-chip cst-chip-warn" data-testid="cst-mode">
              Fixture mode · no server, no Muse
            </span>
          )}
        </p>
      </header>

      <PrivacyGate
        client={getPrivacyClient()}
        communityId={communityId}
        communityName={communityName}
        onDataDeleted={() => {
          client.clearLocalData?.(); // fixture only; the server deletes in live mode
          setEpoch((value) => value + 1);
        }}
      >
        <DailyContent key={epoch} client={client} />
      </PrivacyGate>

      <footer className="cst-footer">
        <span>Unofficial hackathon prototype · Fictional demo content</span>
        {client.isOperator && (
          <Link to={`/groups/${communityId}/constellations/operator`}>Operator console</Link>
        )}
      </footer>
    </main>
  );
}
