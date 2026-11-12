import { useCallback, useEffect, useId, useRef, useState, type FormEvent } from "react";
import type { PrivateIntent } from "../../../../../contracts/protocol";
import {
  INTENT_FIELDS,
  OnboardingError,
  type IntentExtraction,
  type IntentField,
  type OnboardingCommunity,
  type OnboardingPorts,
} from "./types";
import {
  LIMITS,
  buildSubmission,
  emptyForm,
  formFromDraft,
  formatMoney,
  newWindowKey,
  type FieldErrors,
  type IntentForm,
} from "./validation";
import { MAX_RECORDING_SECONDS, useVoiceRecorder } from "./useVoiceRecorder";

export interface IntentOnboardingProps {
  community: OnboardingCommunity;
  ports: OnboardingPorts;
  /**
   * Supplied by the privacy component (Patrik). While false, nothing is sent
   * for transcription, extraction or persistence.
   */
  consentGranted: boolean;
  /** IANA zone used to interpret typed times. Defaults to the browser zone. */
  timeZone?: string;
  /** Fired after the server acknowledges a confirmed intent. */
  onConfirmed?: (intent: PrivateIntent) => void;
  /** Fired when a person reopens a confirmed intent for correction. */
  onEditStarted?: () => void;
}

type Phase = "capture" | "transcribing" | "extracting" | "review" | "submitting" | "confirmed";
type Operation = "transcribe" | "extract" | "confirm";

const QUESTIONS: Record<IntentField, string> = {
  goal: "What would you enjoy doing with a small group?",
  interests: "Which interests should we match you on?",
  areaId: "Where can you meet?",
  availability: "When are you free? Add at least one time window.",
  maxBudgetMinor: "What's the most you'd spend per person? Enter 0 for free activities.",
  maxDurationMinutes: "How long can you spend, at most?",
};
const LABELS: Record<IntentField, string> = {
  goal: "What you'd enjoy",
  interests: "Interests",
  areaId: "Area",
  availability: "When you're free",
  maxBudgetMinor: "Max budget per person",
  maxDurationMinutes: "Max time",
};
const DURATION_OPTIONS = [30, 45, 60, 90, 120, 180, 240];

const isAbort = (error: unknown) => (error as Error)?.name === "AbortError";

function describeError(error: unknown): { message: string; retryable: boolean } {
  if (error instanceof OnboardingError) {
    const byCode: Partial<Record<string, string>> = {
      UNAUTHENTICATED: "Your session has expired. Sign in again to continue.",
      CONSENT_REQUIRED: "Group Quests needs your consent before it can process this.",
      STALE_REVISION: "Your intent changed somewhere else. Reload it before saving.",
      RATE_LIMITED: "Too many requests. Wait a moment and try again.",
      PROVIDER_UNAVAILABLE: "The assistant is unavailable right now.",
      NETWORK: "Could not reach Group Quests. Check your connection.",
      IDEMPOTENCY_CONFLICT: "This save conflicted with an earlier attempt. Review and confirm again.",
    };
    return { message: byCode[error.code] ?? error.message, retryable: error.retryable };
  }
  return { message: "Something went wrong.", retryable: true };
}

function formatWindow(start: string, end: string, timeZone: string) {
  const day = new Intl.DateTimeFormat(undefined, {
    weekday: "short",
    month: "short",
    day: "numeric",
    timeZone,
  }).format(new Date(start));
  const time = new Intl.DateTimeFormat(undefined, {
    hour: "numeric",
    minute: "2-digit",
    timeZone,
  });
  return `${day}, ${time.format(new Date(start))}–${time.format(new Date(end))}`;
}

export default function IntentOnboarding({
  community,
  ports,
  consentGranted,
  timeZone = Intl.DateTimeFormat().resolvedOptions().timeZone,
  onConfirmed,
  onEditStarted,
}: IntentOnboardingProps) {
  const uid = useId();
  const [phase, setPhase] = useState<Phase>("capture");
  const [transcript, setTranscript] = useState("");
  const [voiceUsed, setVoiceUsed] = useState(false);
  const [extraction, setExtraction] = useState<IntentExtraction | null>(null);
  const [form, setForm] = useState<IntentForm>(emptyForm);
  const [errors, setErrors] = useState<FieldErrors>({});
  const [interestDraft, setInterestDraft] = useState("");
  const [opError, setOpError] = useState<{ op: Operation; message: string; retryable: boolean } | null>(null);
  const [confirmed, setConfirmed] = useState<PrivateIntent | null>(null);
  const [status, setStatus] = useState("");
  const lastAudio = useRef<Blob | null>(null);
  const idempotency = useRef<{ body: string; key: string } | null>(null);
  const sequence = useRef(0);
  const controller = useRef<AbortController | null>(null);
  const reviewHeading = useRef<HTMLHeadingElement>(null);
  const captureHeading = useRef<HTMLHeadingElement>(null);
  const confirmedHeading = useRef<HTMLHeadingElement>(null);
  const focusTarget = useRef<"review" | "capture" | "confirmed" | null>(null);

  /** Starts a request; only the most recent request may apply its result. */
  const begin = useCallback(() => {
    controller.current?.abort();
    const ctrl = new AbortController();
    controller.current = ctrl;
    const id = ++sequence.current;
    return { signal: ctrl.signal, isCurrent: () => id === sequence.current && !ctrl.signal.aborted };
  }, []);
  const invalidate = useCallback(() => {
    controller.current?.abort();
    controller.current = null;
    sequence.current++;
  }, []);
  useEffect(() => () => controller.current?.abort(), []);

  useEffect(() => {
    const target = focusTarget.current;
    focusTarget.current = null;
    if (target === "review") reviewHeading.current?.focus();
    if (target === "capture") captureHeading.current?.focus();
    if (target === "confirmed") confirmedHeading.current?.focus();
  }, [phase]);

  /* ---------- transcription ---------- */
  const transcribe = useCallback(
    async (audio: Blob) => {
      lastAudio.current = audio;
      const request = begin();
      setOpError(null);
      setPhase("transcribing");
      setStatus("Transcribing your voice note…");
      try {
        const { transcript: text } = await ports.transcribe(audio, request.signal);
        if (!request.isCurrent()) return;
        lastAudio.current = null;
        setTranscript((previous) =>
          (previous.trim() ? `${previous.trim()} ${text.trim()}` : text.trim()).slice(
            0,
            LIMITS.transcriptChars,
          ),
        );
        setVoiceUsed(true);
        setStatus("Transcript ready. Review and edit it before continuing.");
      } catch (error) {
        if (isAbort(error) || !request.isCurrent()) return;
        setOpError({ op: "transcribe", ...describeError(error) });
        setStatus("Transcription failed.");
      }
      if (request.isCurrent()) setPhase("capture");
    },
    [begin, ports],
  );
  const recorder = useVoiceRecorder(transcribe);

  /* ---------- extraction ---------- */
  const extract = useCallback(async () => {
    const text = transcript.trim();
    if (!text || !consentGranted) return;
    const request = begin();
    setOpError(null);
    setPhase("extracting");
    setStatus("Reading your intent…");
    try {
      const result = await ports.extract({ transcript: text, communityId: community.communityId }, request.signal);
      if (!request.isCurrent()) return;
      setExtraction(result);
      setForm(formFromDraft(result.draft, community));
      setErrors({});
      focusTarget.current = "review";
      setPhase("review");
      setStatus(
        result.missingFields.length
          ? `Review your details. ${result.missingFields.length} still needed.`
          : "Review your details.",
      );
    } catch (error) {
      if (isAbort(error) || !request.isCurrent()) return;
      setOpError({ op: "extract", ...describeError(error) });
      setPhase("capture");
      setStatus("We couldn't read that.");
    }
  }, [begin, community, consentGranted, ports, transcript]);

  /** Typed-only path: skip extraction and fill the fields by hand. */
  const fillManually = () => {
    invalidate();
    setOpError(null);
    setExtraction({ draft: {}, missingFields: [...INTENT_FIELDS], evidence: null });
    setForm({ ...emptyForm(), goal: transcript.trim().slice(0, LIMITS.goalChars) });
    setErrors({});
    focusTarget.current = "review";
    setPhase("review");
    setStatus("Fill in your details.");
  };

  const cancelPending = () => {
    const wasPhase = phase;
    invalidate();
    setOpError(null);
    if (wasPhase === "submitting") {
      setPhase("review");
      setStatus("Stopped waiting. The save may still have reached the server; confirming again is safe.");
    } else {
      focusTarget.current = "capture";
      setPhase("capture");
      setStatus("Cancelled. Your text is unchanged.");
    }
  };

  /* ---------- confirmation ---------- */
  const confirm = async (event?: FormEvent) => {
    event?.preventDefault();
    if (!consentGranted) return;
    const built = buildSubmission(form, community, {
      timeZone,
      expectedVersion: confirmed?.intentVersion ?? 0,
      now: Date.now(),
    });
    if (!built.ok) {
      setErrors(built.errors);
      setStatus(`${Object.keys(built.errors).length} detail(s) need attention.`);
      const first = INTENT_FIELDS.find((f) => built.errors[f]);
      if (first) document.getElementById(`${uid}-${first}`)?.focus();
      return;
    }
    setErrors({});
    // Reuse the key for an identical retry; a changed body gets a new key.
    const body = JSON.stringify(built.submission);
    if (idempotency.current?.body !== body)
      idempotency.current = { body, key: crypto.randomUUID() };
    const request = begin();
    setOpError(null);
    setPhase("submitting");
    setStatus("Saving your confirmed intent…");
    try {
      const intent = await ports.confirm(built.submission, {
        signal: request.signal,
        idempotencyKey: idempotency.current.key,
      });
      if (!request.isCurrent()) return;
      idempotency.current = null;
      setConfirmed(intent);
      focusTarget.current = "confirmed";
      setPhase("confirmed");
      setStatus("Intent confirmed.");
      onConfirmed?.(intent);
    } catch (error) {
      if (isAbort(error) || !request.isCurrent()) return;
      setOpError({ op: "confirm", ...describeError(error) });
      setPhase("review");
      setStatus("Saving failed.");
    }
  };

  const editConfirmed = () => {
    if (!confirmed) return;
    onEditStarted?.();
    setForm(formFromDraft(confirmed, community));
    setExtraction({ draft: confirmed, missingFields: [], evidence: null });
    focusTarget.current = "review";
    setPhase("review");
    setStatus("Editing your confirmed intent. Matching uses the new version after you confirm.");
  };

  const retry = () => {
    if (!opError) return;
    if (opError.op === "transcribe" && lastAudio.current) void transcribe(lastAudio.current);
    else if (opError.op === "extract") void extract();
    else if (opError.op === "confirm") void confirm();
  };

  /* ---------- form helpers ---------- */
  const update = <K extends keyof IntentForm>(key: K, value: IntentForm[K]) =>
    setForm((previous) => ({ ...previous, [key]: value }));
  const addInterest = () => {
    const value = interestDraft.trim().slice(0, LIMITS.interestChars);
    if (!value) return;
    if (form.interests.length >= LIMITS.interests) return;
    if (!form.interests.some((i) => i.toLowerCase() === value.toLowerCase()))
      update("interests", [...form.interests, value]);
    setInterestDraft("");
  };
  const missing = new Set<IntentField>(extraction?.missingFields ?? []);
  const busy = phase === "transcribing" || phase === "extracting" || phase === "submitting";
  const blocked = !consentGranted;

  const errorBanner = opError && (
    <div className="gq-alert gq-alert-error" role="alert">
      <p>{opError.message}</p>
      <div className="gq-row">
        {opError.retryable && (
          <button type="button" className="gq-button gq-button-secondary" onClick={retry}>
            Try again
          </button>
        )}
        {opError.op !== "confirm" && (
          <button type="button" className="gq-button gq-button-ghost" onClick={fillManually}>
            Fill in details myself
          </button>
        )}
      </div>
    </div>
  );

  const pending = busy && (
    <div className="gq-pending" role="status">
      <span className="gq-spinner" aria-hidden="true" />
      <span>
        {phase === "transcribing"
          ? "Transcribing…"
          : phase === "extracting"
            ? "Reading your intent…"
            : "Saving…"}
      </span>
      <button type="button" className="gq-button gq-button-ghost" onClick={cancelPending}>
        {phase === "submitting" ? "Stop waiting" : "Cancel"}
      </button>
    </div>
  );

  return (
    <section className="gq-onboarding" aria-labelledby={`${uid}-title`}>
      <p className="gq-visually-hidden" aria-live="polite">
        {status}
      </p>

      {(phase === "capture" || phase === "transcribing" || phase === "extracting") && (
        <div className="gq-card">
          <h2 id={`${uid}-title`} ref={captureHeading} tabIndex={-1} className="gq-card-title">
            Tell us what you'd enjoy
          </h2>
          <p className="gq-muted">
            Record a short voice note or type it. You'll review everything before anything is shared.
          </p>
          {blocked && (
            <p className="gq-alert gq-alert-info">Turn on Group Quests consent above to continue.</p>
          )}

          <div className="gq-voice">
            {recorder.status === "recording" ? (
              <>
                <button type="button" className="gq-button gq-button-record is-recording" onClick={recorder.stop}>
                  <span className="gq-record-dot" aria-hidden="true" /> Stop recording
                </button>
                <span className="gq-muted" aria-live="off">
                  {recorder.seconds}s / {MAX_RECORDING_SECONDS}s
                </span>
                <button type="button" className="gq-button gq-button-ghost" onClick={recorder.cancel}>
                  Discard
                </button>
              </>
            ) : (
              <button
                type="button"
                className="gq-button gq-button-record"
                onClick={() => void recorder.start()}
                disabled={
                  blocked ||
                  busy ||
                  recorder.status === "unsupported" ||
                  recorder.status === "requesting"
                }
              >
                <span className="gq-record-dot" aria-hidden="true" />
                {recorder.status === "requesting" ? "Waiting for microphone…" : "Record voice note"}
              </button>
            )}
          </div>
          {recorder.status === "unsupported" && (
            <p className="gq-alert gq-alert-info" role="status">
              Voice recording isn't available in this browser. Type your intent below instead.
            </p>
          )}
          {recorder.status === "denied" && (
            <p className="gq-alert gq-alert-info" role="status">
              Microphone access was blocked. You can allow it in your browser settings, or type below.
            </p>
          )}
          {recorder.error && (
            <p className="gq-alert gq-alert-info" role="status">
              {recorder.error} Type your intent below instead.
            </p>
          )}

          <label className="gq-label" htmlFor={`${uid}-transcript`}>
            {voiceUsed ? "Transcript (edit anything that's wrong)" : "Or type it"}
          </label>
          <textarea
            id={`${uid}-transcript`}
            className="gq-textarea"
            rows={4}
            maxLength={LIMITS.transcriptChars}
            value={transcript}
            disabled={busy || blocked}
            placeholder="e.g. A short photo walk this weekend, free or under $10, about an hour."
            onChange={(event) => setTranscript(event.target.value)}
          />
          <div className="gq-row gq-row-between">
            <span className="gq-muted gq-small">
              {transcript.length}/{LIMITS.transcriptChars}
              {voiceUsed && ports.mode === "fixture" && " · Fixture transcript: your audio was not sent anywhere."}
            </span>
          </div>
          {errorBanner}
          {pending}
          <div className="gq-row gq-actions">
            <button
              type="button"
              className="gq-button gq-button-primary"
              disabled={busy || blocked || !transcript.trim()}
              onClick={() => void extract()}
            >
              Continue
            </button>
            <button
              type="button"
              className="gq-button gq-button-ghost"
              disabled={busy || blocked}
              onClick={fillManually}
            >
              Fill in details myself
            </button>
          </div>
        </div>
      )}

      {(phase === "review" || phase === "submitting") && (
        <form className="gq-card" onSubmit={(event) => void confirm(event)} noValidate>
          <h2 id={`${uid}-title`} ref={reviewHeading} tabIndex={-1} className="gq-card-title">
            Confirm your details
          </h2>
          <p className="gq-muted">
            Only you can see these. Matching uses them after you confirm.{" "}
            {extraction?.evidence
              ? `Suggested by ${extraction.evidence.model}${extraction.evidence.source === "replay" ? " (replay)" : ""}.`
              : ports.mode === "fixture"
                ? "Suggestions came from fixture keyword rules, not Muse."
                : ""}
          </p>

          {missing.size > 0 && (
            <div className="gq-alert gq-alert-info">
              <p className="gq-strong">A few things we still need:</p>
              <ul className="gq-questions">
                {INTENT_FIELDS.filter((f) => missing.has(f)).map((field) => (
                  <li key={field}>
                    <a href={`#${uid}-${field}`}>{QUESTIONS[field]}</a>
                  </li>
                ))}
              </ul>
            </div>
          )}

          <fieldset className="gq-fields" disabled={phase === "submitting"}>
            <div className={`gq-field${errors.goal ? " has-error" : ""}`}>
              <label className="gq-label" htmlFor={`${uid}-goal`}>
                {LABELS.goal}
              </label>
              <textarea
                id={`${uid}-goal`}
                className="gq-textarea"
                rows={2}
                maxLength={LIMITS.goalChars}
                value={form.goal}
                aria-invalid={!!errors.goal}
                aria-describedby={errors.goal ? `${uid}-goal-error` : undefined}
                onChange={(event) => update("goal", event.target.value)}
              />
              {errors.goal && <p id={`${uid}-goal-error`} className="gq-error">{errors.goal}</p>}
            </div>

            <div className={`gq-field${errors.interests ? " has-error" : ""}`}>
              <label className="gq-label" htmlFor={`${uid}-interests`}>
                {LABELS.interests}
              </label>
              {form.interests.length > 0 && (
                <ul className="gq-chips" aria-label="Selected interests">
                  {form.interests.map((interest) => (
                    <li key={interest} className="gq-chip">
                      {interest}
                      <button
                        type="button"
                        className="gq-chip-remove"
                        aria-label={`Remove ${interest}`}
                        onClick={() => update("interests", form.interests.filter((i) => i !== interest))}
                      >
                        ×
                      </button>
                    </li>
                  ))}
                </ul>
              )}
              <div className="gq-row">
                <input
                  id={`${uid}-interests`}
                  className="gq-input"
                  value={interestDraft}
                  maxLength={LIMITS.interestChars}
                  placeholder="Add an interest"
                  aria-invalid={!!errors.interests}
                  aria-describedby={errors.interests ? `${uid}-interests-error` : undefined}
                  onChange={(event) => setInterestDraft(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter") {
                      event.preventDefault();
                      addInterest();
                    }
                  }}
                />
                <button
                  type="button"
                  className="gq-button gq-button-secondary"
                  onClick={addInterest}
                  disabled={!interestDraft.trim() || form.interests.length >= LIMITS.interests}
                >
                  Add
                </button>
              </div>
              {errors.interests && (
                <p id={`${uid}-interests-error`} className="gq-error">{errors.interests}</p>
              )}
            </div>

            <div className={`gq-field${errors.areaId ? " has-error" : ""}`}>
              <label className="gq-label" htmlFor={`${uid}-areaId`}>
                {LABELS.areaId}
              </label>
              <select
                id={`${uid}-areaId`}
                className="gq-input"
                value={form.areaId}
                aria-invalid={!!errors.areaId}
                aria-describedby={errors.areaId ? `${uid}-areaId-error` : undefined}
                onChange={(event) => update("areaId", event.target.value)}
              >
                <option value="">Choose an area…</option>
                {community.areas.map((area) => (
                  <option key={area.areaId} value={area.areaId}>
                    {area.name}
                  </option>
                ))}
              </select>
              {errors.areaId && <p id={`${uid}-areaId-error`} className="gq-error">{errors.areaId}</p>}
            </div>

            <fieldset className={`gq-field gq-subfieldset${errors.availability ? " has-error" : ""}`}>
              <legend className="gq-label">
                {LABELS.availability} <span className="gq-muted gq-small">({timeZone})</span>
              </legend>
              {form.availability.map((window, index) => (
                <div className="gq-window" key={window.key}>
                  <label className="gq-mini-label">
                    Date
                    <input
                      id={index === 0 ? `${uid}-availability` : undefined}
                      type="date"
                      className="gq-input"
                      value={window.date}
                      aria-invalid={!!errors.availability}
                      onChange={(event) =>
                        update(
                          "availability",
                          form.availability.map((w) => (w.key === window.key ? { ...w, date: event.target.value } : w)),
                        )
                      }
                    />
                  </label>
                  <label className="gq-mini-label">
                    From
                    <input
                      type="time"
                      className="gq-input"
                      value={window.start}
                      onChange={(event) =>
                        update(
                          "availability",
                          form.availability.map((w) => (w.key === window.key ? { ...w, start: event.target.value } : w)),
                        )
                      }
                    />
                  </label>
                  <label className="gq-mini-label">
                    To
                    <input
                      type="time"
                      className="gq-input"
                      value={window.end}
                      onChange={(event) =>
                        update(
                          "availability",
                          form.availability.map((w) => (w.key === window.key ? { ...w, end: event.target.value } : w)),
                        )
                      }
                    />
                  </label>
                  <button
                    type="button"
                    className="gq-button gq-button-ghost gq-window-remove"
                    aria-label={`Remove time window ${index + 1}`}
                    onClick={() => update("availability", form.availability.filter((w) => w.key !== window.key))}
                  >
                    Remove
                  </button>
                </div>
              ))}
              <button
                type="button"
                id={form.availability.length === 0 ? `${uid}-availability` : undefined}
                className="gq-button gq-button-secondary"
                disabled={form.availability.length >= LIMITS.windows}
                onClick={() =>
                  update("availability", [
                    ...form.availability,
                    { key: newWindowKey(), date: "", start: "", end: "" },
                  ])
                }
              >
                Add a time
              </button>
              {errors.availability && <p className="gq-error">{errors.availability}</p>}
            </fieldset>

            <div className="gq-grid-2">
              <div className={`gq-field${errors.maxBudgetMinor ? " has-error" : ""}`}>
                <label className="gq-label" htmlFor={`${uid}-maxBudgetMinor`}>
                  {LABELS.maxBudgetMinor} ({community.currency})
                </label>
                <input
                  id={`${uid}-maxBudgetMinor`}
                  className="gq-input"
                  inputMode="decimal"
                  placeholder="0 for free"
                  value={form.budget}
                  aria-invalid={!!errors.maxBudgetMinor}
                  aria-describedby={errors.maxBudgetMinor ? `${uid}-budget-error` : undefined}
                  onChange={(event) => update("budget", event.target.value)}
                />
                {errors.maxBudgetMinor && (
                  <p id={`${uid}-budget-error`} className="gq-error">{errors.maxBudgetMinor}</p>
                )}
              </div>
              <div className={`gq-field${errors.maxDurationMinutes ? " has-error" : ""}`}>
                <label className="gq-label" htmlFor={`${uid}-maxDurationMinutes`}>
                  {LABELS.maxDurationMinutes}
                </label>
                <select
                  id={`${uid}-maxDurationMinutes`}
                  className="gq-input"
                  value={form.durationMinutes}
                  aria-invalid={!!errors.maxDurationMinutes}
                  aria-describedby={errors.maxDurationMinutes ? `${uid}-duration-error` : undefined}
                  onChange={(event) => update("durationMinutes", event.target.value)}
                >
                  <option value="">Choose…</option>
                  {[...new Set([...DURATION_OPTIONS, Number(form.durationMinutes) || 0])]
                    .filter(Boolean)
                    .sort((a, b) => a - b)
                    .map((minutes) => (
                      <option key={minutes} value={String(minutes)}>
                        {minutes < 60 ? `${minutes} minutes` : `${minutes / 60} hour${minutes === 60 ? "" : "s"}`}
                      </option>
                    ))}
                </select>
                {errors.maxDurationMinutes && (
                  <p id={`${uid}-duration-error`} className="gq-error">{errors.maxDurationMinutes}</p>
                )}
              </div>
            </div>
          </fieldset>

          {errorBanner}
          {pending}
          <div className="gq-row gq-actions">
            <button type="submit" className="gq-button gq-button-primary" disabled={busy || blocked}>
              Confirm intent
            </button>
            <button
              type="button"
              className="gq-button gq-button-ghost"
              disabled={busy}
              onClick={() => {
                invalidate();
                setOpError(null);
                focusTarget.current = "capture";
                setPhase("capture");
              }}
            >
              Back to my words
            </button>
          </div>
        </form>
      )}

      {phase === "confirmed" && confirmed && (
        <div className="gq-card gq-card-success">
          <h2 id={`${uid}-title`} ref={confirmedHeading} tabIndex={-1} className="gq-card-title">
            Intent confirmed
          </h2>
          <p className="gq-muted">
            Version {confirmed.intentVersion} · private to you
            {ports.mode === "fixture" && " · fixture save, not persisted"}
          </p>
          <dl className="gq-summary" data-testid="gq-confirmed-summary">
            <dt>{LABELS.goal}</dt>
            <dd>{confirmed.goal}</dd>
            <dt>{LABELS.interests}</dt>
            <dd>{confirmed.interests.join(", ")}</dd>
            <dt>{LABELS.areaId}</dt>
            <dd>{community.areas.find((a) => a.areaId === confirmed.areaId)?.name ?? confirmed.areaId}</dd>
            <dt>{LABELS.availability}</dt>
            <dd>
              <ul>
                {confirmed.availability.map((w) => (
                  <li key={w.start}>{formatWindow(w.start, w.end, confirmed.timeZone)}</li>
                ))}
              </ul>
            </dd>
            <dt>{LABELS.maxBudgetMinor}</dt>
            <dd>{formatMoney(confirmed.maxBudgetMinor, confirmed.currency)}</dd>
            <dt>{LABELS.maxDurationMinutes}</dt>
            <dd>{confirmed.maxDurationMinutes} minutes</dd>
          </dl>
          <div className="gq-row gq-actions">
            <button type="button" className="gq-button gq-button-secondary" onClick={editConfirmed}>
              Edit intent
            </button>
          </div>
        </div>
      )}
    </section>
  );
}
