import { useId, useState, type ReactNode } from "react";
import { allOn, PrivacyError, type ActivityInput, type ConsentToggles, type PrivacyClient, type SessionView } from "./client";
import { NO_TOGGLES, PRIVATE_ITEMS, SHARED_ITEMS, TOGGLES } from "./copy";
import { usePrivacySession } from "./usePrivacySession";
import "./privacy.css";

function errorText(error: unknown): string {
  if (error instanceof PrivacyError) return error.message;
  return "Something went wrong. Try again.";
}

export function FixtureBadge({ client }: { client: PrivacyClient }) {
  if (client.mode !== "fixture") return null;
  return (
    <p className="cstp-fixture" data-testid="cstp-fixture">
      Fixture mode · no sign-in, nothing leaves this tab
    </p>
  );
}

/** Private support card: never counsels, points to people who can help. */
export function SupportCard() {
  return (
    <aside className="cstp-support" aria-label="Support" data-testid="cstp-support-card">
      <strong>This stays private.</strong>
      <p>
        It won't be used for matching or shown to anyone. If this week feels heavy, you don't have to carry it alone.
      </p>
      <ul>
        <li>Talk to your campus counseling center. Most offer same-day appointments.</li>
        <li>
          In the US, call or text <a href="tel:988">988</a> (Suicide and Crisis Lifeline), any time, free and
          confidential.
        </li>
        <li>If you are in immediate danger, call 911.</li>
      </ul>
    </aside>
  );
}

function ToggleList({
  value,
  onChange,
  disabled,
}: {
  value: ConsentToggles;
  onChange: (next: ConsentToggles) => void;
  disabled?: boolean;
}) {
  const base = useId();
  return (
    <ul className="cstp-toggles">
      {TOGGLES.map((t) => (
        <li key={t.key}>
          <button
            type="button"
            role="switch"
            aria-checked={value[t.key]}
            aria-describedby={`${base}-${t.key}`}
            className="cstp-switch"
            disabled={disabled}
            data-testid={`cstp-toggle-${t.key}`}
            onClick={() => onChange({ ...value, [t.key]: !value[t.key] })}
          >
            <span className="cstp-switch-track" aria-hidden="true">
              <span className="cstp-switch-thumb" />
            </span>
            <span className="cstp-switch-label">{t.label}</span>
          </button>
          <p id={`${base}-${t.key}`} className="cstp-detail">
            {t.detail}
          </p>
        </li>
      ))}
    </ul>
  );
}

function WhatIsShared() {
  return (
    <div className="cstp-split">
      <section aria-label="Only you see">
        <h3>Only you see</h3>
        <ul>{PRIVATE_ITEMS.map((i) => <li key={i}>{i}</li>)}</ul>
      </section>
      <section aria-label="Others see">
        <h3>Others see</h3>
        <ul>{SHARED_ITEMS.map((i) => <li key={i}>{i}</li>)}</ul>
      </section>
    </div>
  );
}

/** One screen: what is private, what is shared, three toggles (all off), a display name. */
export function JoinScreen({
  client,
  communityId,
  communityName,
  onJoined,
}: {
  client: PrivacyClient;
  communityId: string;
  communityName: string;
  onJoined: (view: SessionView) => void;
}) {
  const [name, setName] = useState("");
  const [toggles, setToggles] = useState<ConsentToggles>(NO_TOGGLES);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const nameId = useId();
  const ready = name.trim().length > 0 && name.trim().length <= 40 && allOn(toggles);

  return (
    <form
      className="cstp-card"
      data-testid="cstp-join"
      onSubmit={(event) => {
        event.preventDefault();
        if (!ready || busy) return;
        setBusy(true);
        setError(null);
        client.join(communityId, name.trim(), toggles).then(
          (view) => onJoined(view),
          (e: unknown) => {
            setError(errorText(e));
            setBusy(false);
          },
        );
      }}
    >
      <FixtureBadge client={client} />
      <h2>Join Facebook Space</h2>
      <p className="cstp-hint">Plays across {communityName}.</p>
      <p className="cstp-lede">
        One honest question a day, Monday to Friday. On Sunday you meet the people whose answers meant the same thing,
        anonymously.
      </p>
      <WhatIsShared />
      <label htmlFor={nameId} className="cstp-label">
        Display name <span className="cstp-hint">(shown only after a mutual reveal)</span>
      </label>
      <input
        id={nameId}
        className="cstp-input"
        value={name}
        maxLength={40}
        autoComplete="nickname"
        onChange={(e) => setName(e.target.value)}
        data-testid="cstp-name"
      />
      <ToggleList value={toggles} onChange={setToggles} disabled={busy} />
      {!allOn(toggles) && (
        <p className="cstp-hint" role="status">
          All three are needed to play. You can turn any of them off later, and it takes effect right away.
        </p>
      )}
      {error && (
        <p className="cstp-error" role="alert">
          {error}
        </p>
      )}
      <button type="submit" className="cstp-primary" disabled={!ready || busy} data-testid="cstp-join-submit">
        {busy ? "Joining…" : "Join this week"}
      </button>
    </form>
  );
}

/**
 * D010: optional fourth switch, off by default and separate from the three
 * required ones. On: sends Group, Event and friend ids plus my own post and
 * comment text, which the server turns into allowlisted topics and discards.
 */
function ActivitySwitch({
  client,
  view,
  disabled,
  collect,
  onChange,
}: {
  client: PrivacyClient;
  view: SessionView;
  disabled: boolean;
  collect: () => ActivityInput;
  onChange: (view: SessionView) => void;
}) {
  const on = view.consent.useActivity === true;
  const [busy, setBusy] = useState(false);
  const [topics, setTopics] = useState<string[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const id = useId();
  return (
    <div className="cstp-activity" data-testid="cstp-activity">
      <h3>Brighten matches with my activity</h3>
      <button
        type="button"
        role="switch"
        aria-checked={on}
        aria-describedby={id}
        className="cstp-switch"
        disabled={disabled || busy}
        data-testid="cstp-toggle-useActivity"
        onClick={() => {
          setBusy(true);
          setError(null);
          client.setActivity(!on, on ? undefined : collect()).then(
            (result) => {
              setBusy(false);
              setTopics(result.useActivity ? result.topics : null);
              onChange({ ...view, consent: { ...view.consent, useActivity: result.useActivity } });
            },
            (e: unknown) => {
              setBusy(false);
              setError(errorText(e));
            },
          );
        }}
      >
        <span className="cstp-switch-track" aria-hidden="true">
          <span className="cstp-switch-thumb" />
        </span>
        <span className="cstp-switch-label">Use my Groups, Events, friends and post topics</span>
      </button>
      <p id={id} className="cstp-detail">
        Optional. People in your Groups or going to the same events shine a little brighter. Your posts and comments
        are reduced to everyday topics like "music" or "coffee"; the words themselves are never kept or shown.
        Turning this off deletes it.
      </p>
      {on && topics && (
        <p className="cstp-ok" role="status" data-testid="cstp-activity-topics">
          {topics.length ? `Topics found: ${topics.join(", ")}` : "No topics found in your posts yet."}
        </p>
      )}
      {error && (
        <p className="cstp-error" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}

/** Consent changes (version-checked), delete my data, sign out. */
export function PrivacySettings({
  client,
  view,
  onChange,
  onSignedOut,
  onDataDeleted,
  collectActivity,
}: {
  client: PrivacyClient;
  view: SessionView;
  onChange: (view: SessionView) => void;
  onSignedOut: () => void;
  onDataDeleted?: () => void;
  /** D010: when given, shows the optional "use my activity" switch. */
  collectActivity?: () => ActivityInput;
}) {
  const current: ConsentToggles = {
    matchAnswers: view.consent.matchAnswers,
    anonymousChat: view.consent.anonymousChat,
    isAdult: view.consent.isAdult,
  };
  const [draft, setDraft] = useState<ConsentToggles>(current);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const dirty = (Object.keys(draft) as (keyof ConsentToggles)[]).some((k) => draft[k] !== current[k]);
  const withdrawing = (Object.keys(draft) as (keyof ConsentToggles)[]).some((k) => current[k] && !draft[k]);

  function run(action: () => Promise<void>) {
    setBusy(true);
    setError(null);
    setNotice(null);
    action().then(
      () => setBusy(false),
      (e: unknown) => {
        setBusy(false);
        if (e instanceof PrivacyError && e.code === "STALE_REVISION") {
          setError("Your settings changed on another screen. Showing the latest.");
          client.session(view.consent.communityId).then((fresh) => (fresh ? onChange(fresh) : onSignedOut()), () => {});
          return;
        }
        if (e instanceof PrivacyError && e.code === "UNAUTHENTICATED") {
          onSignedOut();
          return;
        }
        setError(errorText(e));
      },
    );
  }

  return (
    <section className="cstp-card" data-testid="cstp-settings" aria-label="Privacy and data">
      <FixtureBadge client={client} />
      <h2>Privacy and data</h2>
      <p className="cstp-status" data-testid="cstp-status" role="status">
        {allOn(current) ? "You're playing this week." : "Paused: turn all three on to keep playing."}
      </p>
      <ToggleList value={draft} onChange={setDraft} disabled={busy} />
      {withdrawing && (
        <p className="cstp-warn" role="status">
          Turning this off takes effect immediately: you leave this week's matching and your constellation's chat.
        </p>
      )}
      {notice && (
        <p className="cstp-ok" role="status" data-testid="cstp-notice">
          {notice}
        </p>
      )}
      {error && (
        <p className="cstp-error" role="alert">
          {error}
        </p>
      )}
      <div className="cstp-row">
        <button
          type="button"
          className="cstp-primary"
          disabled={!dirty || busy}
          data-testid="cstp-save"
          onClick={() =>
            run(async () => {
              const consent = await client.updateConsent(view.consent.version, draft);
              onChange({ ...view, consent });
              setNotice("Saved.");
            })
          }
        >
          Save
        </button>
      </div>

      {collectActivity && (
        <ActivitySwitch
          client={client}
          view={view}
          disabled={busy || !allOn(current)}
          collect={collectActivity}
          onChange={onChange}
        />
      )}

      <h3>Delete my data</h3>
      <p className="cstp-detail">
        Deletes every answer you've written and your event interests and RSVPs, now. Answers are also deleted automatically 14 days after each
        week locks.
      </p>
      {!confirmDelete ? (
        <button type="button" className="cstp-danger" disabled={busy} onClick={() => setConfirmDelete(true)}
          data-testid="cstp-delete">
          Delete my answers and event data
        </button>
      ) : (
        <div className="cstp-row" role="group" aria-label="Confirm delete">
          <button
            type="button"
            className="cstp-danger"
            disabled={busy}
            data-testid="cstp-delete-confirm"
            onClick={() =>
              run(async () => {
                await client.deleteMyData();
                setConfirmDelete(false);
                setNotice("Your answers and event data were deleted.");
                onDataDeleted?.();
              })
            }
          >
            Yes, delete them
          </button>
          <button type="button" className="cstp-secondary" disabled={busy} onClick={() => setConfirmDelete(false)}>
            Cancel
          </button>
        </div>
      )}

      <div className="cstp-row cstp-signout">
        <button
          type="button"
          className="cstp-secondary"
          disabled={busy}
          data-testid="cstp-signout"
          onClick={() => run(async () => { await client.signOut(); onSignedOut(); })}
        >
          Sign out on this device
        </button>
      </div>
    </section>
  );
}

/**
 * Wrap the Facebook Space page: shows the join screen until this Group's
 * session exists with all three consents, then renders ``children`` with a
 * collapsible "Privacy and data" panel. ``onDataDeleted`` lets the page refresh.
 */
export function PrivacyGate({
  client,
  communityId,
  communityName,
  children,
  onDataDeleted,
  collectActivity,
}: {
  client: PrivacyClient;
  communityId: string;
  communityName: string;
  children: ReactNode;
  onDataDeleted?: () => void;
  collectActivity?: () => ActivityInput;
}) {
  const { state, reload, set } = usePrivacySession(client, communityId);

  if (state.status === "loading") {
    return <p className="cstp-loading" role="status">Loading…</p>;
  }
  if (state.status === "error") {
    return (
      <div className="cstp-card" role="alert">
        <p>{state.message}</p>
        {state.retryable && (
          <button type="button" className="cstp-secondary" onClick={reload}>
            Try again
          </button>
        )}
      </div>
    );
  }
  if (state.status === "signed_out") {
    return <JoinScreen client={client} communityId={communityId} communityName={communityName} onJoined={set} />;
  }
  const settings = (
    <PrivacySettings
      key={state.view.consent.version}
      client={client}
      view={state.view}
      onChange={set}
      onSignedOut={() => set(null)}
      onDataDeleted={onDataDeleted}
      collectActivity={collectActivity}
    />
  );
  if (!allOn(state.view.consent)) return settings;
  return (
    <>
      {children}
      <details className="cstp-panel" data-testid="cstp-panel">
        <summary>Privacy and data</summary>
        {settings}
      </details>
    </>
  );
}
