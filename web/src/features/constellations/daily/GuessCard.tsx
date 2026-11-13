import { useState, type CSSProperties } from "react";
import { Check, Users } from "lucide-react";
import type { CycleClient } from "./client";
import { message } from "./useDaily";

/** Private prevalence guess, styled like a Facebook poll. */
export default function GuessCard({ client, cycleId, saved }: { client: CycleClient; cycleId: string; saved: number | null }) {
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
    <section className="card cst-panel" aria-labelledby="cst-guess-title">
      <header className="cst-panel-head">
        <span className="cst-icon-circle" aria-hidden="true">
          <Users size={18} />
        </span>
        <div>
          <h2 id="cst-guess-title">How many people here feel like you this week?</h2>
          <p className="muted">Private guess · revealed in Sunday's Sky next to the real number</p>
        </div>
      </header>
      <div className="cst-guess">
        <output className="cst-guess-value" htmlFor="cst-guess" aria-hidden="true">
          {value}%
        </output>
        <label className="sr-only" htmlFor="cst-guess">
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
      </div>
      <div className="cst-panel-foot">
        {stored !== null && (
          <span className="cst-saved-note" role="status">
            <Check size={14} aria-hidden="true" /> Saved: {stored}%
          </span>
        )}
        <button type="button" className="button-primary" onClick={() => void save()} disabled={busy || stored === value}>
          {stored === null ? "Save guess" : stored === value ? "Guess saved" : "Update guess"}
        </button>
      </div>
      {error && (
        <p className="cst-error" role="alert">
          {error}
        </p>
      )}
    </section>
  );
}
