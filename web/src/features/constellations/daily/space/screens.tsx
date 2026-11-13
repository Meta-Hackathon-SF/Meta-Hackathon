/* Light (Facebook-style) Space screens: answer, follow-up, support, events, invite, privacy, join, empty home bar. */
import { StageOptIn } from "../../stage/StageOptIn";
import { useState } from "react";
import { Settings } from "lucide-react";
import type { ConsentToggles, PrivacyClient, SessionView } from "../../privacy";
import type { CycleClient, CycleDay, DailyQuestion } from "../client";
import { MAX_CHARS } from "../useDaily";
import { DAY_LONG, dayHex, type Screen } from "./model";
import { Glyph, MicIcon, StarField, Toggle, TopBar, Waveform } from "./parts";
import { SUPPORT_RESOURCES } from "./preview";
import { useVoiceInput } from "./useVoiceInput";

export type Go = (screen: Screen, day?: number) => void;

// ---------------------------------------------------------------- home
export function HomeBar({ go, fixture }: { go: Go; fixture: boolean }) {
  return (
    <div className="spc-homebar">
      <h1 className="spc-brand">
        Space
        <span className="sr-only"> · Facebook Space</span>
      </h1>
      {fixture && (
        <span className="spc-mode" data-testid="cst-mode">
          Fixture mode · no server, no Muse
        </span>
      )}
      <div className="spc-homebar-actions">
        <button type="button" className="spc-round is-gray" onClick={() => go("sky")} aria-label="Week sky">
          <Glyph size={20} color="#050505" />
        </button>
        <button type="button" className="spc-round is-gray" onClick={() => go("settings")} aria-label="Privacy and data">
          <Settings size={20} />
        </button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------- answer / follow-up / support
export function AnswerScreen({
  client,
  question,
  day,
  isToday,
  initial,
  onBack,
  onSubmit,
  busy,
  error,
}: {
  client: CycleClient;
  question: DailyQuestion | undefined;
  day: CycleDay;
  isToday: boolean;
  initial: string;
  onBack: () => void;
  onSubmit: (text: string, source: "voice" | "text") => void;
  busy: boolean;
  error: string | null;
}) {
  const [draft, setDraft] = useState(initial);
  const voice = useVoiceInput(client, setDraft);
  const title = isToday ? `${DAY_LONG[day - 1]} · ${day} of 5` : `Catch up · ${DAY_LONG[day - 1]}`;
  return (
    <div className="spc-screen spc-white">
      <TopBar title={title} onBack={onBack} dot={dayHex(day)} />
      <div className="spc-pad spc-col">
        <div className="spc-qcard">
          <StarField />
          <p>{question?.question.text ?? "Loading…"}</p>
        </div>
        {voice.recording ? (
          <div className="spc-listening is-box">
            <Waveform />
            {draft ? (
              <p className="spc-live-text" aria-live="polite">
                {draft}
              </p>
            ) : (
              <span>Listening… tap the mic to stop</span>
            )}
          </div>
        ) : (
          <textarea
            className="spc-textarea"
            aria-label="Your answer"
            value={draft}
            onChange={(e) => setDraft(e.target.value.slice(0, MAX_CHARS))}
            maxLength={MAX_CHARS}
          />
        )}
        <div className="spc-row spc-between">
          <button
            type="button"
            className={`spc-mic is-gray${voice.recording ? " is-on" : ""}`}
            onClick={voice.toggle}
            disabled={voice.blocked}
            aria-label={voice.recording ? "Stop recording" : "Answer by voice"}
            aria-pressed={voice.recording}
          >
            <MicIcon />
          </button>
          <span className="spc-hint" aria-live="polite">
            {voice.hint === "or just talk" ? `${draft.length}/${MAX_CHARS}` : voice.hint}
          </span>
        </div>
        <p className="spc-fine">Only you can see your answer.</p>
        {error && (
          <p className="spc-error" role="alert">
            {error}
          </p>
        )}
        <div className="spc-flex" />
        <button type="button" className="spc-btn spc-btn-primary spc-btn-lg" disabled={!draft.trim() || busy} onClick={() => onSubmit(draft.trim(), voice.source)}>
          {busy ? "Saving…" : initial ? "Save changes" : "Submit"}
        </button>
      </div>
    </div>
  );
}

export function FollowUpScreen({ question, onSkip, onSend, busy, error, evidence, room }: { question: string; onSkip: () => void; onSend: (text: string) => void; busy: boolean; error: string | null; evidence: string; room: number }) {
  const [reply, setReply] = useState("");
  const over = reply.trim().length > room;
  return (
    <div className="spc-screen spc-white">
      <TopBar title="One more thing" onBack={onSkip} />
      <div className="spc-pad spc-col">
        <p className="spc-fu-q">{question}</p>
        <span className="spc-fine" data-testid="cst-muse-chip">
          {evidence}
        </span>
        <textarea className="spc-textarea is-short" aria-label={question} value={reply} onChange={(e) => setReply(e.target.value)} />
        <span className={`spc-fine${over ? " spc-count-over" : ""}`} data-testid="spc-fu-count">
          {reply.trim().length}/{room}
          {over ? " · too long to add to your answer" : ""}
        </span>
        {error && (
          <p className="spc-error" role="alert">
            {error}
          </p>
        )}
        <div className="spc-flex" />
        <div className="spc-row">
          <button type="button" className="spc-btn spc-btn-gray spc-btn-lg spc-grow" onClick={onSkip}>
            Skip
          </button>
          <button type="button" className="spc-btn spc-btn-primary spc-btn-lg spc-grow" disabled={!reply.trim() || over || busy} onClick={() => onSend(reply.trim())}>
            Send
          </button>
        </div>
      </div>
    </div>
  );
}

function Resources() {
  return (
    <div className="spc-card spc-rounded spc-list">
      {SUPPORT_RESOURCES.map((r, i) => (
        <div className="spc-list-row is-static" key={r.name}>
          <span className="spc-list-main">
            {r.name}
            <small>{r.sub}</small>
          </span>
          <a className={`spc-btn ${i === 0 ? "spc-btn-primary" : "spc-btn-tint"} spc-btn-sm`} href={r.href} target={r.href.startsWith("http") ? "_blank" : undefined} rel="noreferrer">
            {r.action}
          </a>
        </div>
      ))}
    </div>
  );
}

export function DistressScreen({ onBack }: { onBack: () => void }) {
  return (
    <div className="spc-screen">
      <TopBar title="Just for you" onBack={onBack} />
      <div className="spc-pad spc-col" data-testid="spc-support">
        <div className="spc-card spc-rounded spc-pad-lg">
          <h3 className="spc-h3">Thanks for telling us.</h3>
          <p>This answer stays private and won't be used in the game. If things feel heavy right now, you can talk to someone today.</p>
        </div>
        <Resources />
        <button type="button" className="spc-btn spc-btn-gray spc-btn-lg" onClick={onBack}>
          Back to Space
        </button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------- events / invite

export function EventsScreen({ onBack, eventsOn, enable }: { onBack: () => void; eventsOn: boolean; enable: () => void }) {
  return (
    <div className="spc-screen">
      <TopBar title="Where your people are going" onBack={onBack} />
      <div className="spc-pad spc-col">
        {!eventsOn && (
          <div className="spc-card spc-rounded spc-row spc-pad-md">
            <span className="spc-grow spc-strong">See where your people go</span>
            <button type="button" className="spc-btn spc-btn-primary spc-btn-sm" onClick={enable}>
              Turn on
            </button>
          </div>
        )}
        <section className="spc-card spc-empty" data-testid="spc-events-empty">
          <h2>Nothing yet</h2>
          <p className="spc-sub">Events your people are interested in will show up here.</p>
        </section>
        <p className="spc-fine">Interest is private. Groups under 3 people are never shown.</p>
      </div>
    </div>
  );
}

export function InviteScreen({ onBack }: { onBack: () => void }) {
  return (
    <div className="spc-screen spc-white">
      <TopBar title="You're invited" onBack={onBack} />
      <div className="spc-pad spc-col">
        <section className="spc-card spc-empty" data-testid="spc-invite-empty">
          <h2>No invites yet</h2>
          <p className="spc-sub">When an event your people want to go to is on, it will show up here.</p>
        </section>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------- privacy
export interface LocalPrefs {
  events: boolean;
  voice: boolean;
}

export function SettingsScreen({
  view,
  privacy,
  prefs,
  setPrefs,
  onBack,
  onConsent,
  onDeleted,
}: {
  view: SessionView;
  privacy: PrivacyClient;
  prefs: LocalPrefs;
  setPrefs: (p: LocalPrefs) => void;
  onBack: () => void;
  onConsent: (view: SessionView) => void;
  onDeleted: () => void;
}) {
  const [step, setStep] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const c = view.consent;
  const run = async (work: () => Promise<void>) => {
    setBusy(true);
    setError(null);
    try {
      await work();
    } catch (err) {
      setError((err as Error).message || "Something went wrong.");
    } finally {
      setBusy(false);
    }
  };
  const setConsent = (key: keyof ConsentToggles) =>
    run(async () => {
      const toggles = { matchAnswers: c.matchAnswers, anonymousChat: c.anonymousChat, isAdult: c.isAdult, [key]: !c[key] };
      const consent = await privacy.updateConsent(c.version, toggles);
      onConsent({ ...view, consent });
    });
  const setActivity = () =>
    run(async () => {
      const on = !c.useActivity;
      await privacy.setActivity(on);
      onConsent({ ...view, consent: { ...c, useActivity: on } });
    });
  const rows: { label: string; sub: string; on: boolean; go: () => void; key: string }[] = [
    { key: "match", label: "Match me by my answers", sub: "Muse reads them privately", on: c.matchAnswers, go: () => void setConsent("matchAnswers") },
    { key: "chat", label: "Anonymous chat", sub: "Sunday chat with your constellation", on: c.anonymousChat, go: () => void setConsent("anonymousChat") },
    { key: "activity", label: "Use my activity", sub: "Groups and events you follow help with questions", on: Boolean(c.useActivity), go: () => void setActivity() },
    { key: "events", label: "Event signals", sub: "Private interest in events", on: prefs.events, go: () => setPrefs({ ...prefs, events: !prefs.events }) },
    { key: "voice", label: "Voice answers", sub: "Audio is never kept", on: prefs.voice, go: () => setPrefs({ ...prefs, voice: !prefs.voice }) },
  ];
  return (
    <div className="spc-screen">
      <TopBar title="Privacy and data" onBack={onBack} />
      <div className="spc-pad spc-col" data-testid="cstp-panel">
        <div className="spc-card spc-rounded spc-list is-flush">
          {rows.map((r) => (
            <div className="spc-list-row is-static is-divided" key={r.key}>
              <span className="spc-list-main is-normal">
                {r.label}
                <small>{r.sub}</small>
              </span>
              <Toggle on={r.on} label={r.label} onChange={r.go} disabled={busy} testId={`spc-set-${r.key}`} />
            </div>
          ))}
        </div>
        {error && (
          <p className="spc-error" role="alert">
            {error}
          </p>
        )}
        <StageOptIn />
        <div className="spc-card spc-rounded spc-pad-md spc-col is-tight">
          <button type="button" className="spc-btn spc-btn-gray" disabled={busy} onClick={() => void run(async () => { await privacy.signOut(); onDeleted(); })}>
            Sign out
          </button>
          {step === 0 && (
            <button type="button" className="spc-link-danger" onClick={() => setStep(1)}>
              Delete all my data
            </button>
          )}
          {step === 1 && (
            <>
              <div className="spc-strong">Delete everything?</div>
              <p className="spc-sub">Your answers, interests and RSVPs are deleted and your star leaves every constellation. This can't be undone.</p>
              <div className="spc-row">
                <button type="button" className="spc-btn spc-btn-gray spc-grow" onClick={() => setStep(0)}>
                  Cancel
                </button>
                <button
                  type="button"
                  className="spc-btn spc-btn-danger spc-grow"
                  disabled={busy}
                  onClick={() =>
                    void run(async () => {
                      await privacy.deleteMyData();
                      onDeleted();
                    })
                  }
                >
                  Delete
                </button>
              </div>
            </>
          )}
        </div>
        <div className="spc-card spc-rounded spc-pad-md spc-col is-tight">
          <div className="spc-strong">Need to talk to someone?</div>
          {SUPPORT_RESOURCES.map((r) => (
            <div className="spc-row spc-between" key={r.name}>
              <span>{r.name}</span>
              <a className="spc-link" href={r.href} target={r.href.startsWith("http") ? "_blank" : undefined} rel="noreferrer">
                {r.action}
              </a>
            </div>
          ))}
        </div>
        <p className="spc-fine">Answers are deleted 30 days after the week ends. Chats are deleted 7 days after they close.</p>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------- join
const JOIN_ROWS: { key: keyof ConsentToggles | "events" | "voice"; label: string; sub: string; required?: boolean }[] = [
  { key: "matchAnswers", label: "Match me by my answers", sub: "Muse reads them privately.", required: true },
  { key: "anonymousChat", label: "Anonymous chat", sub: "Sunday, as a star.", required: true },
  { key: "events", label: "Event signals", sub: "See where your people are going." },
  { key: "voice", label: "Voice answers", sub: "Never kept." },
  { key: "isAdult", label: "I'm 18 or older", sub: "Required.", required: true },
];

export function JoinScreen({
  privacy,
  communityId,
  displayName,
  onJoined,
  onBack,
}: {
  privacy: PrivacyClient;
  communityId: string;
  displayName: string;
  onJoined: (view: SessionView, prefs: LocalPrefs) => void;
  onBack?: () => void;
}) {
  const [on, setOn] = useState<Record<string, boolean>>({ matchAnswers: false, anonymousChat: false, events: false, voice: false, isAdult: false });
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const all = JOIN_ROWS.every((r) => on[r.key]);
  const ready = name.trim().length > 0 && JOIN_ROWS.filter((r) => r.required).every((r) => on[r.key]);
  const join = async () => {
    if (!ready || busy) return;
    setBusy(true);
    setError(null);
    try {
      const view = await privacy.join(communityId, name.trim(), { matchAnswers: on.matchAnswers, anonymousChat: on.anonymousChat, isAdult: on.isAdult });
      onJoined(view, { events: on.events, voice: on.voice });
    } catch (err) {
      setError((err as Error).message || "Couldn't join. Try again.");
      setBusy(false);
    }
  };
  return (
    <div className="spc-screen spc-white" data-testid="cstp-join">
      <TopBar title="Join Facebook Space" onBack={onBack} />
      <div className="spc-pad-xl spc-col is-loose">
        <div>
          <h3 className="spc-h1">Before you play</h3>
          <p className="spc-sub is-lg">Nothing is saved until you join.</p>
          <p className="spc-sub">Simulated Facebook profile: {displayName} is not a verified identity.</p>
          <label className="spc-field-label" htmlFor="spc-display-name">Display name</label>
          <input className="spc-name-input" aria-describedby="spc-name-help" id="spc-display-name" maxLength={40} autoComplete="nickname" value={name} onChange={(e) => setName(e.target.value)} data-testid="cstp-name" />
          <p className="spc-fine" id="spc-name-help">Your name is shared only when you both choose to reveal.</p>
        </div>
        <div className="spc-selectall">
          <span className="spc-strong">Select all</span>
          <Toggle
            on={all}
            label="Select all"
            onChange={() => setOn(Object.fromEntries(JOIN_ROWS.map((r) => [r.key, !all])))}
            testId="spc-join-all"
          />
        </div>
        {JOIN_ROWS.map((r) => (
          <div className="spc-join-row" key={r.key}>
            <div className="spc-grow">
              <div className="spc-strong is-600">{r.label}</div>
              <div className="spc-sub">{r.sub}</div>
            </div>
            <Toggle on={on[r.key]} label={r.label} onChange={() => setOn({ ...on, [r.key]: !on[r.key] })} testId={`cstp-toggle-${r.key}`} />
          </div>
        ))}
        {error && (
          <p className="spc-error" role="alert">
            {error}
          </p>
        )}
        <div className="spc-flex" />
        <button type="button" className="spc-btn spc-btn-primary spc-btn-lg" disabled={!ready || busy} onClick={() => void join()} data-testid="cstp-join-submit">
          {busy ? "Joining…" : "Join Facebook Space"}
        </button>
        <a href="/space/operator">Demo host sign in</a>
        <p className="spc-from">
          from <b>Meta</b>
        </p>
      </div>
    </div>
  );
}
