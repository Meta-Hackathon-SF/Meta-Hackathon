import { useId, useState } from "react";
import type { Consent } from "../../../../../contracts/protocol";
import type { ConsentToggles, MembershipView, PrivacyClient } from "./client";
import { CONSENT_COPY, CONSENT_KEYS as KEYS } from "./consent";
import { isMatchable } from "./consent";
import { toApiError } from "./usePrivacySession";
import styles from "./privacy.module.css";

function Switch({
  name,
  checked,
  disabled,
  onChange,
}: {
  name: keyof ConsentToggles;
  checked: boolean;
  disabled?: boolean;
  onChange: (value: boolean) => void;
}) {
  const id = useId();
  const copy = CONSENT_COPY[name];
  return (
    <div className={styles.toggleRow}>
      <div>
        <label htmlFor={id} className={styles.toggleLabel}>{copy.label}</label>
        <p id={`${id}-d`} className={styles.toggleDetail}>{copy.detail}</p>
      </div>
      <button
        id={id}
        type="button"
        role="switch"
        aria-checked={checked}
        aria-describedby={`${id}-d`}
        disabled={disabled}
        className={styles.switch}
        data-on={checked}
        onClick={() => onChange(!checked)}
      >
        <span className={styles.knob} />
      </button>
    </div>
  );
}

export function ConsentToggleList({
  value,
  disabled,
  onChange,
}: {
  value: ConsentToggles;
  disabled?: boolean;
  onChange: (value: ConsentToggles) => void;
}) {
  return (
    <div className={styles.toggleList}>
      {KEYS.map((key) => (
        <Switch key={key} name={key} checked={value[key]} disabled={disabled}
          onChange={(v) => onChange({ ...value, [key]: v })} />
      ))}
    </div>
  );
}

export interface ConsentPanelProps {
  client: PrivacyClient;
  membership: MembershipView;
  /** Called with the saved consent revision. */
  onSaved?: (consent: Consent) => void;
  /** Called after a STALE_REVISION so the parent can reload the session. */
  onStale?: () => void;
}

/** Edit consent with optimistic-concurrency (expectedVersion). */
export function ConsentPanel({ client, membership, onSaved, onStale }: ConsentPanelProps) {
  const saved = membership.consent;
  const [draft, setDraft] = useState<ConsentToggles>(pick(saved));
  const [status, setStatus] = useState<{ kind: "idle" | "saving" | "saved" | "error"; message?: string }>({ kind: "idle" });
  const dirty = KEYS.some((k) => draft[k] !== saved[k]);
  const withdrawing = KEYS.some((k) => saved[k] && !draft[k]);

  async function save() {
    setStatus({ kind: "saving" });
    try {
      const next = await client.updateConsent(membership.communityId, saved.version, draft);
      setStatus({ kind: "saved", message: `Saved as version ${next.version}.` });
      onSaved?.(next);
    } catch (error) {
      const e = toApiError(error);
      if (e.code === "STALE_REVISION") {
        setStatus({ kind: "error", message: "Your settings changed on another device. We reloaded the latest version." });
        onStale?.();
      } else {
        setStatus({ kind: "error", message: e.message });
      }
    }
  }

  return (
    <section className={styles.card} aria-labelledby="gq-consent-title">
      <header className={styles.cardHeader}>
        <h3 id="gq-consent-title" className={styles.cardTitle}>Your privacy choices</h3>
        <span className={styles.version}>Version {saved.version}</span>
      </header>
      <MatchableStatus consent={saved} />
      <ConsentToggleList value={draft} disabled={status.kind === "saving"} onChange={(v) => { setDraft(v); setStatus({ kind: "idle" }); }} />
      {withdrawing && dirty && (
        <p className={styles.warning} role="note">
          Turning this off takes effect right away. You’ll be removed from new matches, and any plan still being prepared with you is stopped.
        </p>
      )}
      <div className={styles.actions}>
        <button type="button" className={styles.primary} disabled={!dirty || status.kind === "saving"} onClick={save}>
          {status.kind === "saving" ? "Saving…" : "Save choices"}
        </button>
        {dirty && (
          <button type="button" className={styles.secondary} onClick={() => { setDraft(pick(saved)); setStatus({ kind: "idle" }); }}>
            Undo changes
          </button>
        )}
      </div>
      <p className={styles.status} role={status.kind === "error" ? "alert" : "status"} aria-live="polite">
        {status.message ?? ""}
      </p>
    </section>
  );
}

export function MatchableStatus({ consent }: { consent: Consent }) {
  const ok = isMatchable(consent);
  return (
    <p className={styles.pill} data-tone={ok ? "ok" : "off"}>
      {ok ? "You can be matched" : "Not matchable: matching and Muse processing are both required"}
    </p>
  );
}

function pick(c: ConsentToggles): ConsentToggles {
  return { matching: c.matching, modelProcessing: c.modelProcessing, publicInterests: c.publicInterests };
}
