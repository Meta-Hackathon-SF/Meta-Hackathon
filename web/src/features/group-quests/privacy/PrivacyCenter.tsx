import { useEffect, useId, useState } from "react";
import type { FormEvent } from "react";
import type { Consent, PrivateIntent } from "../../../../../contracts/protocol";
import type { ConsentToggles, MembershipView, PrivacyClient } from "./client";
import { ConsentPanel, ConsentToggleList } from "./ConsentControls";
import { formatMoney, isMatchable } from "./consent";
import { toApiError, usePrivacySession } from "./usePrivacySession";
import styles from "./privacy.module.css";

const NONE: ConsentToggles = { matching: false, modelProcessing: false, publicInterests: false };

export function FixtureBadge({ client }: { client: PrivacyClient }) {
  if (client.mode !== "fixture") return null;
  return <span className={styles.fixture} title="Local fixture data. Nothing is saved to the server.">Fixture mode</span>;
}

export interface JoinCommunityCardProps {
  client: PrivacyClient;
  communityId: string;
  communityName: string;
  onJoined: (membership: MembershipView) => void;
}

/** Consent-first join. Every toggle starts off; nothing is pre-granted. */
export function JoinCommunityCard({ client, communityId, communityName, onJoined }: JoinCommunityCardProps) {
  const nameId = useId();
  const [displayName, setDisplayName] = useState("");
  const [consent, setConsent] = useState<ConsentToggles>(NONE);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const trimmed = displayName.trim();

  async function join(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      onJoined(await client.join(communityId, trimmed, consent));
    } catch (e) {
      setError(toApiError(e).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className={styles.card} onSubmit={join} aria-labelledby={`${nameId}-t`}>
      <header className={styles.cardHeader}>
        <h3 id={`${nameId}-t`} className={styles.cardTitle}>Join {communityName}</h3>
        <FixtureBadge client={client} />
      </header>
      <label htmlFor={nameId} className={styles.fieldLabel}>Display name</label>
      <input id={nameId} className={styles.input} value={displayName} maxLength={40} autoComplete="nickname"
        onChange={(e) => setDisplayName(e.target.value)} placeholder="What your group will call you" required />
      <p className={styles.toggleDetail}>Choose what you allow. You can change these at any time.</p>
      <ConsentToggleList value={consent} disabled={busy} onChange={setConsent} />
      {!isMatchable(consent) && (
        <p className={styles.note}>You can join without matching. Turn on both of the first two choices when you want a group.</p>
      )}
      <div className={styles.actions}>
        <button type="submit" className={styles.primary} disabled={!trimmed || busy}>
          {busy ? "Joining…" : "Join community"}
        </button>
      </div>
      {error && <p className={styles.status} role="alert">{error}</p>}
    </form>
  );
}

export interface PublicPreviewProps {
  displayName: string;
  consent: Pick<Consent, "publicInterests">;
  /** Your own confirmed intent, if any. Shown only to you. */
  intent?: PrivateIntent | null;
}

/** Side-by-side: what group members see versus what stays private. */
export function PublicPreview({ displayName, consent, intent }: PublicPreviewProps) {
  const interests = consent.publicInterests ? intent?.interests ?? [] : [];
  return (
    <section className={styles.card} aria-labelledby="gq-preview-title">
      <h3 id="gq-preview-title" className={styles.cardTitle}>What others see</h3>
      <div className={styles.previewGrid}>
        <div className={styles.previewPublic}>
          <p className={styles.previewHeading}>Your group sees</p>
          <p className={styles.previewName}>{displayName}</p>
          {consent.publicInterests ? (
            interests.length ? (
              <ul className={styles.chips} aria-label="Public interests">
                {interests.map((i) => <li key={i}>{i}</li>)}
              </ul>
            ) : (
              <p className={styles.toggleDetail}>Your interests will appear here once you confirm them.</p>
            )
          ) : (
            <p className={styles.toggleDetail}>Interests hidden</p>
          )}
        </div>
        <div className={styles.previewPrivate}>
          <p className={styles.previewHeading}>Only you see</p>
          <dl className={styles.privateList}>
            <dt>Goal</dt><dd>{intent?.goal ?? "Not set"}</dd>
            <dt>Budget</dt><dd>{intent ? formatMoney(intent.maxBudgetMinor, intent.currency) : "Not set"}</dd>
            <dt>Availability</dt><dd>{intent ? `${intent.availability.length} time window${intent.availability.length === 1 ? "" : "s"}` : "Not set"}</dd>
          </dl>
          <p className={styles.toggleDetail}>
            Group members never see these. Group explanations describe the group (“a free activity fits everyone”), never one person’s limits.
          </p>
        </div>
      </div>
    </section>
  );
}

export interface LeaveCommunityProps {
  client: PrivacyClient;
  communityId: string;
  communityName: string;
  onLeft: (consent: Consent) => void;
}

/** Two-step leave. Withdraws all consent and deletes your private intent. */
export function LeaveCommunity({ client, communityId, communityName, onLeft }: LeaveCommunityProps) {
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function leave() {
    setBusy(true);
    setError(null);
    try {
      onLeft(await client.leave(communityId));
    } catch (e) {
      setError(toApiError(e).message);
      setBusy(false);
    }
  }

  return (
    <section className={styles.dangerZone} aria-label="Leave community">
      {!confirming ? (
        <button type="button" className={styles.danger} onClick={() => setConfirming(true)}>
          Leave {communityName}
        </button>
      ) : (
        <div role="group" aria-label="Confirm leaving">
          <p className={styles.toggleDetail}>
            This withdraws all permissions and deletes your saved goal, budget and times for {communityName}.
          </p>
          <div className={styles.actions}>
            <button type="button" className={styles.danger} disabled={busy} onClick={leave} autoFocus>
              {busy ? "Leaving…" : "Yes, leave and delete"}
            </button>
            <button type="button" className={styles.secondary} disabled={busy} onClick={() => setConfirming(false)}>Cancel</button>
          </div>
        </div>
      )}
      {error && <p className={styles.status} role="alert">{error}</p>}
    </section>
  );
}

export interface PrivacyCenterProps {
  client: PrivacyClient;
  communityId: string;
  communityName: string;
  /** Fires when matchability changes so the shell can gate "Find my group". */
  onMatchableChange?: (matchable: boolean) => void;
}

/** Composed privacy area for Will's feature shell. */
export function PrivacyCenter({ client, communityId, communityName, onMatchableChange }: PrivacyCenterProps) {
  const { state, reload, start } = usePrivacySession(client);
  const [intent, setIntent] = useState<PrivateIntent | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const membership = state.status === "ready"
    ? state.session.memberships.find((m) => m.communityId === communityId) ?? null
    : null;
  const matchable = membership ? isMatchable(membership.consent) : false;

  useEffect(() => {
    onMatchableChange?.(matchable);
  }, [matchable, onMatchableChange]);

  const intentVersion = membership?.intentVersion ?? null;
  useEffect(() => {
    if (intentVersion === null) return;
    const ac = new AbortController();
    client.getIntent(communityId, ac.signal).then(setIntent).catch(() => {});
    return () => ac.abort();
  }, [client, communityId, intentVersion]);

  if (state.status === "loading") {
    return <p className={styles.card} aria-busy="true">Loading your privacy settings…</p>;
  }
  if (state.status === "error") {
    return (
      <div className={styles.card} role="alert">
        <p>{state.error.message}</p>
        <button type="button" className={styles.secondary} onClick={() => void reload()}>Try again</button>
      </div>
    );
  }
  if (state.status === "signed_out") {
    return (
      <section className={styles.card}>
        <header className={styles.cardHeader}>
          <h3 className={styles.cardTitle}>Start Group Quests on this device</h3>
          <FixtureBadge client={client} />
        </header>
        <p className={styles.toggleDetail}>
          Creates a private Group Quests profile for this device. It isn’t linked to your Facebook account.
        </p>
        <div className={styles.actions}>
          <button type="button" className={styles.primary} onClick={() => void start()}>Continue</button>
        </div>
      </section>
    );
  }
  if (!membership) {
    return (
      <div className={styles.stack}>
        {notice && <p className={styles.note} role="status">{notice}</p>}
        <JoinCommunityCard client={client} communityId={communityId} communityName={communityName}
          onJoined={() => { setNotice(null); void reload(); }} />
      </div>
    );
  }
  return (
    <div className={styles.stack}>
      {client.mode === "fixture" && <FixtureBadge client={client} />}
      {notice && <p className={styles.note} role="status">{notice}</p>}
      <ConsentPanel
        key={membership.consent.version}
        client={client}
        membership={membership}
        onSaved={(c) => { setNotice(`Choices saved (version ${c.version}).`); void reload(); }}
        onStale={() => void reload()}
      />
      <PublicPreview displayName={membership.displayName} consent={membership.consent} intent={intentVersion === null ? null : intent} />
      <LeaveCommunity client={client} communityId={communityId} communityName={communityName}
        onLeft={() => { setNotice(`You left ${communityName}. Your private details were deleted.`); void reload(); }} />
    </div>
  );
}
