import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router";
import { Check, Flame, Lock, Mic, Pencil, Sparkles, Square, Trash2 } from "lucide-react";
import {
  ClientError,
  type CurrentCycle,
  type CycleClient,
  type CycleDay,
  type DailyAnswer,
  type DailyQuestion,
  type FollowUp,
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
    if (error.code === "CONSENT_REQUIRED") return "Turn on consent to keep playing.";
    return error.message;
  }
  return "Something went wrong. Try again.";
}

function when(iso: string): string {
  return new Date(iso).toLocaleString(undefined, { weekday: "long", hour: "numeric", minute: "2-digit" });
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
    void refresh();
    const unsubscribe = client.subscribe(() => void refresh());
    return () => {
      request.current++;
      unsubscribe();
    };
  }, [client, refresh]);

  return { data, error, refresh };
}

/** One question: answer by voice or text, then edit or delete until lock. */
function AnswerCard({
  client,
  cycleId,
  item,
  answer,
  isToday,
  onChanged,
}: {
  client: CycleClient;
  cycleId: string;
  item: DailyQuestion;
  answer: DailyAnswer | undefined;
  isToday: boolean;
  onChanged: () => void;
}) {
  const [text, setText] = useState("");
  const [source, setSource] = useState<"voice" | "text">("text");
  const [editing, setEditing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [voiceNote, setVoiceNote] = useState<string | null>(null);
  const [support, setSupport] = useState(false);
  const [followUp, setFollowUp] = useState<FollowUp | null>(null);
  const [reply, setReply] = useState("");
  const [skipped, setSkipped] = useState(false);
  const transcription = useRef<AbortController | null>(null);
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
    } catch (err) {
      if (controller.signal.aborted) return;
      setVoiceNote(`${message(err)} You can type your answer instead.`);
    }
  });
  useEffect(() => () => transcription.current?.abort(), []);

  const micBlocked = recorder.status === "denied" || recorder.status === "unsupported";

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
      setSupport(false);
      setFollowUp(null);
      onChanged();
    });

  const showForm = !answer || editing;
  const trimmed = text.trim();

  return (
    <section className="cst-card" aria-labelledby={`cst-q-${day}`} data-testid={`cst-day-${day}`}>
      <p className="cst-eyebrow">
        {isToday ? "Today" : answer && !answer.isCatchUp ? "Earlier this week" : "Catch-up"} · {DAY_NAMES[day - 1]}
      </p>
      <h2 id={`cst-q-${day}`} className="cst-question">
        {item.question.text}
      </h2>
      {!isToday && !answer && (
        <p className="cst-note">Catch-up answers still count toward your constellation, at a lower weight. They don't extend your streak.</p>
      )}

      {showForm ? (
        <form
          onSubmit={(event) => {
            event.preventDefault();
            if (trimmed && !busy) void save();
          }}
        >
          <label className="cst-label" htmlFor={fieldId}>
            {answer ? "Edit your answer" : "Your answer"}
          </label>
          <textarea
            id={fieldId}
            className="cst-textarea"
            rows={4}
            maxLength={MAX_CHARS}
            value={text}
            placeholder="Only you can read this. Type it, or record it."
            onChange={(event) => {
              setText(event.target.value);
              if (!event.target.value) setSource("text");
            }}
          />
          <div className="cst-row cst-row-between">
            <span className="cst-count" aria-live="off">
              {text.length}/{MAX_CHARS}
            </span>
            {recorder.status === "recording" ? (
              <button type="button" className="button-secondary" onClick={recorder.stop}>
                <Square size={16} /> Stop ({recorder.seconds}s of {MAX_RECORDING_SECONDS}s)
              </button>
            ) : (
              <button
                type="button"
                className="button-secondary"
                onClick={() => void recorder.start()}
                disabled={micBlocked || recorder.status === "requesting" || busy}
              >
                <Mic size={16} /> Record answer
              </button>
            )}
          </div>
          <p className="cst-note" role="status">
            {recorder.status === "denied" && "Microphone access is off. Typing works the same."}
            {recorder.status === "unsupported" && "This browser can't record. Typing works the same."}
            {recorder.status === "error" && `${recorder.error ?? "Recording failed."} You can type instead.`}
            {recorder.status !== "denied" && recorder.status !== "unsupported" && recorder.status !== "error" && voiceNote}
          </p>
          <div className="cst-row">
            <button type="submit" className="button-primary" disabled={!trimmed || busy}>
              {busy ? "Saving…" : answer ? "Save changes" : "Submit answer"}
            </button>
            {answer && (
              <button type="button" className="button-secondary" onClick={() => setEditing(false)} disabled={busy}>
                Cancel
              </button>
            )}
          </div>
        </form>
      ) : (
        <div>
          <p className="cst-answer" data-testid={`cst-answer-text-${day}`}>
            {answer.text}
          </p>
          <p className="cst-note">
            <Check size={14} aria-hidden="true" /> Saved{answer.isCatchUp ? " as catch-up" : ""} · private to you ·{" "}
            {answer.source === "voice" ? "from voice" : "typed"}
          </p>
          <div className="cst-row">
            <button
              type="button"
              className="button-secondary"
              onClick={() => {
                setText(answer.text);
                setEditing(true);
              }}
              disabled={busy}
            >
              <Pencil size={16} /> Edit
            </button>
            <button type="button" className="button-secondary" onClick={() => void remove()} disabled={busy}>
              <Trash2 size={16} /> Delete
            </button>
          </div>
        </div>
      )}

      {error && (
        <p className="cst-error" role="alert">
          {error}
        </p>
      )}

      {support && (
        <aside className="cst-support" aria-label="Support" data-testid="cst-support-card">
          <strong>This stays private.</strong> It won't be used for matching or shown to anyone. If this week is
          heavy, campus counseling can help, and in the US you can call or text 988 (Suicide and Crisis Lifeline)
          any time.
        </aside>
      )}

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
          <label className="cst-label" htmlFor={`cst-reply-${day}`}>
            {followUp.question}
          </label>
          <textarea
            id={`cst-reply-${day}`}
            className="cst-textarea"
            rows={2}
            maxLength={Math.max(0, MAX_CHARS - answer.text.length - 1)}
            value={reply}
            onChange={(event) => setReply(event.target.value)}
          />
          <div className="cst-row">
            <button type="submit" className="button-primary" disabled={!reply.trim() || busy}>
              Add to my answer
            </button>
            <button type="button" className="button-secondary" onClick={() => setSkipped(true)}>
              Skip
            </button>
          </div>
        </form>
      )}
    </section>
  );
}

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
    <section className="cst-card" aria-labelledby="cst-guess-title">
      <h2 id="cst-guess-title" className="cst-question">
        How many people here feel like you this week?
      </h2>
      <p className="cst-note">Your guess is private. On Sunday the Sky shows how close the group's guesses were.</p>
      <label className="cst-label" htmlFor="cst-guess">
        Your guess: <strong>{value}%</strong>
      </label>
      <input
        id="cst-guess"
        className="cst-slider"
        type="range"
        min={0}
        max={100}
        step={1}
        value={value}
        onChange={(event) => setValue(Number(event.target.value))}
      />
      <div className="cst-row">
        <button type="button" className="button-primary" onClick={() => void save()} disabled={busy || stored === value}>
          {stored === null ? "Save guess" : stored === value ? "Guess saved" : "Update guess"}
        </button>
        {stored !== null && (
          <span className="cst-note" role="status">
            Saved: {stored}%
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

function WeekStrip({ current, answers }: { current: CurrentCycle; answers: DailyAnswer[] }) {
  const { cycle } = current;
  return (
    <ol className="cst-week" aria-label="This week">
      {DAY_NAMES.map((name, index) => {
        const day = index + 1;
        const answer = answers.find((a) => a.day === day);
        const open = cycle.status === "open";
        const state = answer
          ? answer.isCatchUp
            ? "Caught up"
            : "Answered"
          : open && day === cycle.currentDay
            ? "Today"
            : open && day > cycle.currentDay
              ? "Upcoming"
              : "Missed";
        return (
          <li key={name} className={`cst-day cst-day-${state.toLowerCase().replace(" ", "-")}`}>
            <span className="cst-day-name" aria-hidden="true">
              {name.slice(0, 3)}
            </span>
            <span className="cst-day-state">
              <span className="cst-sr">{name}: </span>
              {state}
            </span>
          </li>
        );
      })}
    </ol>
  );
}

export default function DailyPage() {
  const { communityId = "" } = useParams();
  const communityName = COMMUNITIES[communityId];
  const client = getCycleClient(communityId);
  const { data, error, refresh } = useDaily(client);

  if (!communityName) {
    return (
      <main className="cst-page" id="main-content">
        <h1>Group not found</h1>
        <Link className="button-soft" to="/groups">
          Back to Groups
        </Link>
      </main>
    );
  }

  const current = data?.current ?? null;
  const cycle = current?.cycle;
  const answerFor = (day: number) => data?.answers.find((a) => a.day === day);
  const questionFor = (day: CycleDay) => data?.questions.find((q) => q.day === day);

  return (
    <main className="cst-page" id="main-content">
      <header className="cst-header">
        <p className="cst-breadcrumb">
          <Link to="/groups">Groups</Link> · {communityName}
        </p>
        <div className="cst-row cst-row-between">
          <h1>Constellations</h1>
          {current && (
            <span className="cst-chip cst-chip-streak" data-testid="cst-streak" title="Days in a row answered on the day">
              <Flame size={14} aria-hidden="true" /> Streak {current.streak.current}
            </span>
          )}
        </div>
        <p className="cst-chips">
          <span className="cst-chip">Simulated Facebook</span>
          {client.mode === "fixture" && (
            <span className="cst-chip cst-chip-warn" data-testid="cst-mode">
              Fixture mode · no server, no Muse
            </span>
          )}
          {cycle?.demoTiming && <span className="cst-chip cst-chip-warn">Demo timing</span>}
        </p>
        <p className="cst-lede">
          One question a day, Monday to Friday. On Sunday you meet the 3 to 5 people whose week sounded most like
          yours. Nobody else ever reads your answers.
        </p>
      </header>

      {error && (
        <div className="cst-card">
          <p className="cst-error" role="alert">
            {error}
          </p>
          <button type="button" className="button-secondary" onClick={() => void refresh()}>
            Try again
          </button>
        </div>
      )}

      {!data && !error && <p className="cst-note">Loading this week…</p>}

      {data && !current && (
        <section className="cst-card">
          <h2 className="cst-question">No week is running yet</h2>
          <p className="cst-note">The next week opens Monday morning. Check back then.</p>
        </section>
      )}

      {data && current && cycle && (
        <>
          <WeekStrip current={current} answers={data.answers} />

          {cycle.status === "open" && current.question && (
            <AnswerCard
              key={`${cycle.cycleId}-today-${current.question.day}`}
              client={client}
              cycleId={cycle.cycleId}
              item={current.question}
              answer={answerFor(current.question.day)}
              isToday
              onChanged={() => void refresh()}
            />
          )}

          {cycle.status === "open" &&
            [1, 2, 3, 4, 5]
              .filter((day) => day < cycle.currentDay)
              .map((day) => {
                const item = questionFor(day as CycleDay);
                const answer = answerFor(day);
                if (!item) return null;
                return (
                  <AnswerCard
                    key={`${cycle.cycleId}-${day}`}
                    client={client}
                    cycleId={cycle.cycleId}
                    item={item}
                    answer={answer}
                    isToday={false}
                    onChanged={() => void refresh()}
                  />
                );
              })}

          {cycle.status === "open" && current.catchUp.missedDays.length > 0 && (
            <p className="cst-note" data-testid="cst-catchup-note">
              {current.catchUp.missedDays.length} missed {current.catchUp.missedDays.length === 1 ? "day" : "days"} to
              catch up. Catch-up closes {when(current.catchUp.closesAt)}.
            </p>
          )}

          {cycle.status === "open" && (
            <GuessCard key={cycle.cycleId} client={client} cycleId={cycle.cycleId} saved={data.guess} />
          )}

          {cycle.status !== "open" && (
            <section className="cst-card" data-testid="cst-locked">
              <h2 className="cst-question">
                <Lock size={18} aria-hidden="true" />{" "}
                {cycle.status === "locked" || cycle.status === "forming"
                  ? "This week is locked"
                  : cycle.status === "revealed"
                    ? "Your constellation is out"
                    : "This week has ended"}
              </h2>
              <p className="cst-note">
                {cycle.status === "locked" || cycle.status === "forming"
                  ? `Answers are final. Constellations are revealed ${when(cycle.revealsAt)}.`
                  : cycle.status === "revealed"
                    ? `You answered ${data.answers.length} of 5 questions. Your constellation's chat stays open until ${when(cycle.chatExpiresAt)}.`
                    : "A new week opens Monday morning."}
              </p>
            </section>
          )}
        </>
      )}

      <p className="cst-footer">
        Unofficial hackathon prototype · Fictional demo content
        {client.isOperator && (
          <>
            {" · "}
            <Link to={`/groups/${communityId}/constellations/operator`}>Operator console</Link>
          </>
        )}
      </p>
    </main>
  );
}
