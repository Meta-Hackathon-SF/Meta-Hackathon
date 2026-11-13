/*
 * Phone-side control for the presenter screen. The stage shows the two newest
 * players automatically; here a player can pin a slot or take themselves off.
 */
import { useEffect, useState } from "react";
import { chooseSlot, fetchMySlot, stageAvailable, type SlotChoice } from "./client";

const CHOICES: { value: SlotChoice; label: string }[] = [
  { value: null, label: "Auto" },
  { value: "A", label: "Phone A" },
  { value: "B", label: "Phone B" },
  { value: "off", label: "Hide me" },
];

export function StageOptIn() {
  const [slot, setSlot] = useState<SlotChoice>(null);
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
  const pick = async (value: SlotChoice) => {
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
      <p className="spc-sub">During the live demo, the two newest players appear on the presenter's screen with their name and answers. Pick a side or hide yourself.</p>
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
            data-testid={`stage-optin-${c.value ?? "auto"}`}
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
