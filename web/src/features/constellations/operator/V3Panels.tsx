/*
 * v3 operator controls (owner: Will). PENDING contract 3.0.0 (D012, PRD-v3 S15).
 * Close day: runs day-close formation for a released day ("Demo timing").
 * Custom-event queue removed from the visible UI.
 */
import { useState } from "react";
import { CalendarCheck2 } from "lucide-react";
import { ClientError, type CycleClient, type CycleDay, type WeeklyCycle } from "../daily/client";
import { DAY_NAMES } from "../daily/useDaily";
import { dayStyle } from "../daily/v3";

function explain(error: unknown): string {
  if (error instanceof ClientError) {
    if (error.code === "NOT_FOUND") return "Not available yet: the server hasn't mounted this route.";
    if (error.code === "STALE_REVISION") return error.message || "Already done.";
    if (error.code === "FORBIDDEN") return "This account isn't an operator for this Group.";
    return `${error.code}: ${error.message}`;
  }
  return "Something went wrong.";
}

export function CloseDayControl({ client, cycle, onDone }: { client: CycleClient; cycle: WeeklyCycle; onDone: () => void }) {
  const v3 = client.v3;
  const released = cycle.status === "open" ? cycle.currentDay : 5;
  // The pick resets to the newest released day whenever the cycle moves on.
  const [picked, setPicked] = useState<{ released: number; day: CycleDay } | null>(null);
  const day = picked && picked.released === released ? picked.day : (released as CycleDay);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<{ ok: boolean; text: string } | null>(null);
  if (!v3 || cycle.status !== "open") return null;

  const close = async () => {
    setBusy(true);
    setNote(null);
    try {
      const { jobId } = await v3.closeDay(cycle.cycleId, day);
      setNote({ ok: true, text: `${DAY_NAMES[day - 1]} closed. Day-close formation started (${jobId}).` });
      onDone();
    } catch (err) {
      setNote({ ok: false, text: explain(err) });
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="cst-op-close" data-testid="cst-op-close-day">
      <label className="cst-op-close-pick" style={dayStyle(day)}>
        <span className="sr-only">Day to close</span>
        <select value={day} onChange={(e) => setPicked({ released, day: Number(e.target.value) as CycleDay })} disabled={busy}>
          {Array.from({ length: released }, (_, i) => (i + 1) as CycleDay).map((d) => (
            <option key={d} value={d}>
              {DAY_NAMES[d - 1]}
            </option>
          ))}
        </select>
      </label>
      <button type="button" className="button-secondary" disabled={busy} onClick={() => void close()}>
        <CalendarCheck2 size={16} aria-hidden="true" /> Close day
      </button>
      <span className="cst-label cst-label-warn">Demo timing</span>
      {note && (
        <p className={note.ok ? "cst-op-status" : "cst-error"} role={note.ok ? "status" : "alert"}>
          {note.text}
        </p>
      )}
    </div>
  );
}
