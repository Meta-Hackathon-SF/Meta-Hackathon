/*
 * Phone-side opt-in for the presenter screen. Only the player can put their own
 * answers on stage; the default is off.
 */
import { useEffect, useState } from "react";
import { chooseSlot, fetchMySlot, stageAvailable, type Slot } from "./client";

const CHOICES: { value: Slot | null; label: string }[] = [
  { value: null, label: "Off" },
  { value: "A", label: "Phone A" },
  { value: "B", label: "Phone B" },
];

export function StageOptIn() {
  const [slot, setSlot] = useState<Slot | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    if (!stageAvailable) return;
    const ctl = new AbortController();
    fetchMySlot(ctl.signal)
      .then(setSlot)
      .catch(() => undefined);
    return () => ctl.abort();
  }, []);
  if (!stageAvailable) return null;
  const pick = async (value: Slot | null) => {
    setBusy(true);
    setError(null);
    try {
      setSlot(await chooseSlot(value));
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="spc-card spc-rounded spc-pad-md spc-col is-tight" data-testid="stage-optin">
      <div className="spc-strong">Demo screen</div>
      <p className="spc-sub">Show my answers and my constellation on the presenter's screen. Only for the live demo. Off unless you turn it on.</p>
      <div className="spc-row" role="radiogroup" aria-label="Demo screen">
        {CHOICES.map((c) => (
          <button
            key={c.label}
            type="button"
            role="radio"
            aria-checked={slot === c.value}
            className={`spc-btn spc-btn-sm spc-grow ${slot === c.value ? "spc-btn-primary" : "spc-btn-gray"}`}
            disabled={busy}
            onClick={() => void pick(c.value)}
            data-testid={`stage-optin-${c.value ?? "off"}`}
          >
            {c.label}
          </button>
        ))}
      </div>
      {error && (
        <p className="spc-error" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}
