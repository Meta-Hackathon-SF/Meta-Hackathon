/*
 * One daily question, laid out like a Facebook post with a comment thread:
 * the question, your private answer as a comment, Muse's optional follow-up
 * as a reply. Answering works by typing (Enter sends) or by voice.
 */
import { useEffect, useLayoutEffect, useRef, useState, type ReactNode } from "react";
import { Lock, Mic, Send, Sparkles, Square } from "lucide-react";
import Avatar from "../../../components/common/Avatar";
import Modal from "../../../components/common/Modal";
import { currentUser } from "../../../data/demo";
import ConstellationsMark from "./ConstellationsMark";
import { SupportCard } from "../privacy";
import type { CycleClient, DailyAnswer, DailyQuestion, FollowUp } from "./client";
import { DAY_NAMES, MAX_CHARS, message } from "./useDaily";
import { MAX_RECORDING_SECONDS, useVoiceRecorder } from "./useVoiceRecorder";

export type PostKind = "today" | "catch-up" | "earlier";

function clock(seconds: number): string {
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;
}

/** Grows with its content, like Facebook's comment box. */
function useAutosize(value: string) {
  const ref = useRef<HTMLTextAreaElement | null>(null);
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 220)}px`;
    el.style.overflowY = el.scrollHeight > 220 ? "auto" : "hidden";
  }, [value]);
  return ref;
}

function ReplyBox({
  label,
  placeholder,
  value,
  onChange,
  onSubmit,
  submitLabel,
  disabled,
  busy,
  tools,
  onEscape,
  maxLength = MAX_CHARS,
  avatar = true,
}: {
  label: string;
  placeholder: string;
  value: string;
  onChange: (value: string) => void;
  onSubmit: () => void;
  submitLabel: string;
  disabled?: boolean;
  busy?: boolean;
  tools?: ReactNode;
  onEscape?: () => void;
  maxLength?: number;
  avatar?: boolean;
}) {
  const ref = useAutosize(value);
  const ready = value.trim().length > 0 && !disabled && !busy;
  return (
    <form
      className="cst-reply"
      onSubmit={(event) => {
        event.preventDefault();
        if (ready) onSubmit();
      }}
    >
      {avatar && <Avatar person={currentUser} size={32} />}
      <div className="cst-reply-box">
        <textarea
          ref={ref}
          aria-label={label}
          className="cst-reply-input"
          rows={1}
          maxLength={maxLength}
          value={value}
          placeholder={placeholder}
          onChange={(event) => onChange(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
              event.preventDefault();
              if (ready) onSubmit();
            } else if (event.key === "Escape" && onEscape) {
              event.preventDefault();
              onEscape();
            }
          }}
        />
        <div className="cst-reply-tools">
          {value.length > maxLength - 60 && (
            <span className="cst-count">
              {value.length}/{maxLength}
            </span>
          )}
          {tools}
          <button type="submit" className="cst-send" aria-label={submitLabel} title={submitLabel} disabled={!ready}>
            <Send size={18} fill="currentColor" strokeWidth={1.5} aria-hidden="true" />
          </button>
        </div>
      </div>
    </form>
  );
}

export default function QuestionPost({
  client,
  cycleId,
  item,
  answer,
  kind,
  onChanged,
  framed = true,
  backdrop,
}: {
  client: CycleClient;
  cycleId: string;
  item: DailyQuestion;
  answer: DailyAnswer | undefined;
  kind: PostKind;
  onChanged: () => void;
  /** false = render inside another card (the home feed card supplies its own header). */
  framed?: boolean;
  /** Decorative layer drawn behind the question on the colored panel. */
  backdrop?: ReactNode;
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
  const day = item.day;

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
          : "Check the transcript, edit if needed, then send.",
      );
    } catch (err) {
      if (controller.signal.aborted) return;
      setVoiceNote(`${message(err)} You can type your answer instead.`);
    }
  });
  useEffect(() => () => transcription.current?.abort(), []);

  const recording = recorder.status === "recording";
  const micBlocked = recorder.status === "denied" || recorder.status === "unsupported";
  const note =
    recorder.status === "denied"
      ? "Microphone access is off. Typing works the same."
      : recorder.status === "unsupported"
        ? "This browser can't record. Typing works the same."
        : recorder.status === "error"
          ? `${recorder.error ?? "Recording failed."} You can type instead.`
          : recording
            ? "Recording… tap stop when you're done."
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

  const save = () =>
    run(async () => {
      const result = answer
        ? await client.edit(cycleId, day, { text })
        : await client.submit(cycleId, { day, text, source });
      setSupport(result.supportCard);
      setEditing(false);
      setText("");
      setVoiceNote(null);
      if (!answer && !result.supportCard) {
        client.followUp(cycleId, day).then(setFollowUp, () => setFollowUp(null));
      }
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

  const mic = recording ? (
    <button
      type="button"
      className="cst-tool is-live"
      onClick={recorder.stop}
      aria-label={`Stop recording, ${recorder.seconds} of ${MAX_RECORDING_SECONDS} seconds`}
    >
      <Square size={13} fill="currentColor" aria-hidden="true" />
      <span aria-hidden="true">{clock(recorder.seconds)}</span>
    </button>
  ) : (
    <button
      type="button"
      className="cst-tool"
      aria-label="Record answer"
      title="Record answer"
      onClick={() => void recorder.start()}
      disabled={micBlocked || recorder.status === "requesting" || busy}
    >
      <Mic size={18} aria-hidden="true" />
    </button>
  );

  const eyebrow = kind === "today" ? "Today" : kind === "earlier" ? "Earlier this week" : "Catch-up";
  const showComposer = !answer || editing;

  const body = (
    <>
      {framed && kind !== "today" && (
        <header className="cst-post-head is-compact">
          <span className="cst-day-badge" aria-hidden="true">
            {DAY_NAMES[day - 1].slice(0, 3)}
          </span>
          <div className="cst-post-who">
            <span className="cst-post-title">
              {eyebrow} · {DAY_NAMES[day - 1]}
            </span>
            <span className="post-meta">
              <Lock size={12} aria-hidden="true" /> Only you see your answer
            </span>
          </div>
        </header>
      )}
      {framed && kind === "today" && (
        <header className="cst-post-head">
          <ConstellationsMark />
          <div className="cst-post-who">
            <span className="cst-post-title">
              Constellations
            </span>
            <span className="post-meta">
              <span>
                {eyebrow} · {DAY_NAMES[day - 1]}
              </span>
              <span aria-hidden="true">·</span>
              <Lock size={12} aria-label="Private" />
            </span>
          </div>
        </header>
      )}

      {kind === "today" ? (
        <div className="cst-bg-post">
          {backdrop && (
            <div className="cst-bg-backdrop" aria-hidden="true">
              {backdrop}
            </div>
          )}
          <h2 id={`cst-q-${day}`}>{item.question.text}</h2>
        </div>
      ) : (
        <h2 id={`cst-q-${day}`} className="cst-post-text">
          {item.question.text}
        </h2>
      )}

      {kind === "catch-up" && !answer && (
        <p className="cst-post-note">Catch-up answers count at a lower weight and don't extend your streak.</p>
      )}

      <div className="cst-thread">
        {answer && !editing && (
          <div className="cst-comment">
            <Avatar person={currentUser} size={32} />
            <div className="cst-comment-body">
              <div className="cst-bubble">
                <strong>You</strong>
                <p data-testid={`cst-answer-text-${day}`}>{answer.text}</p>
              </div>
              <div className="cst-comment-actions">
                <span>
                  Saved{answer.isCatchUp ? " as catch-up" : ""} · private to you ·{" "}
                  {answer.source === "voice" ? "from voice" : "typed"}
                </span>
                <button
                  type="button"
                  onClick={() => {
                    setText(answer.text);
                    setEditing(true);
                  }}
                  disabled={busy}
                >
                  Edit
                </button>
                <button type="button" onClick={() => setConfirmDelete(true)} disabled={busy}>
                  Delete
                </button>
              </div>
            </div>
          </div>
        )}

        {answer && !editing && followUp?.needsFollowup && !answer.followUpUsed && !skipped && (
          <div className="cst-comment is-reply">
            <span className="cst-muse-avatar" aria-hidden="true">
              <Sparkles size={16} />
            </span>
            <div className="cst-comment-body">
              <div className="cst-bubble is-muse">
                <strong>Muse</strong>
                <span className="cst-muse-chip" data-testid="cst-muse-chip">
                  {client.mode === "fixture"
                    ? "Fixture follow-up · not Muse"
                    : followUp.evidence
                      ? `${followUp.evidence.model} · ${followUp.evidence.source === "replay" ? "Replay of a saved cycle" : "live"} · ${(followUp.evidence.latencyMs / 1000).toFixed(1)} s`
                      : "AI follow-up"}
                </span>
                <p>{followUp.question}</p>
              </div>
              <ReplyBox
                label={followUp.question}
                placeholder="Add a little more (optional)…"
                value={reply}
                onChange={setReply}
                onSubmit={() => void sendReply()}
                submitLabel="Add to my answer"
                busy={busy}
                maxLength={Math.max(1, MAX_CHARS - answer.text.length - 1)}
                avatar={false}
              />
              <div className="cst-comment-actions">
                <span>Only you see this</span>
                <button type="button" onClick={() => setSkipped(true)}>
                  Skip
                </button>
              </div>
            </div>
          </div>
        )}

        {showComposer && (
          <>
            <ReplyBox
              label={answer ? "Edit your answer" : "Your answer"}
              placeholder={answer ? "Edit your answer…" : "Answer privately…"}
              value={text}
              onChange={(value) => {
                setText(value);
                if (!value) setSource("text");
              }}
              onSubmit={() => void save()}
              submitLabel={answer ? "Save changes" : "Submit answer"}
              disabled={recording}
              busy={busy}
              tools={mic}
              onEscape={answer ? () => setEditing(false) : undefined}
            />
            <p className="cst-reply-note" role="status">
              {note ??
                (answer ? (
                  <>
                    Press Esc to{" "}
                    <button type="button" className="cst-link-button" onClick={() => setEditing(false)}>
                      cancel
                    </button>
                    .
                  </>
                ) : (
                  <>
                    <Lock size={12} aria-hidden="true" /> Only you can see your answer. Muse reads it privately to
                    find your people.
                  </>
                ))}
            </p>
          </>
        )}

        {error && (
          <p className="cst-error" role="alert">
            {error}
          </p>
        )}
        {support && <SupportCard />}
      </div>

      {confirmDelete && answer && (
        <Modal title="Delete answer?" onClose={() => setConfirmDelete(false)}>
          <div className="cst-modal-body">
            <p>
              This removes your answer for {DAY_NAMES[day - 1]}. You can answer again until the week locks on Saturday.
            </p>
            <div className="cst-modal-actions">
              <button type="button" className="cst-button-plain" onClick={() => setConfirmDelete(false)}>
                Cancel
              </button>
              <button type="button" className="button-primary" onClick={() => void remove()} disabled={busy}>
                Delete
              </button>
            </div>
          </div>
        </Modal>
      )}
    </>
  );

  return framed ? (
    <article
      className={`card cst-post is-${kind}`}
      id={`cst-day-${day}`}
      data-testid={`cst-day-${day}`}
      aria-labelledby={`cst-q-${day}`}
    >
      {body}
    </article>
  ) : (
    <div className={`cst-post-inner is-${kind}`} id={`cst-feed-day-${day}`} data-testid={`cst-day-${day}`}>
      {body}
    </div>
  );
}
