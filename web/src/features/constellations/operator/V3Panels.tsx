/*
 * v3 operator controls (owner: Will). PENDING contract 3.0.0 (D012, PRD-v3 S15).
 * Close day: runs day-close formation for a released day ("Demo timing").
 * Custom-event queue: Muse proposes, an operator approves or rejects; nothing is
 * visible to players until approved, and it still needs 3+ RSVPs to run.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { CalendarCheck2, Check, PartyPopper, X } from "lucide-react";
import { ClientError, type CycleClient, type CycleDay, type WeeklyCycle } from "../daily/client";
import { DAY_NAMES } from "../daily/useDaily";
import { dayStyle, type CustomEventProposal, type ProposalDecision } from "../daily/v3";

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
  const [day, setDay] = useState<CycleDay>(released as CycleDay);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<{ ok: boolean; text: string } | null>(null);
  useEffect(() => setDay(released as CycleDay), [released]);
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
        <select value={day} onChange={(e) => setDay(Number(e.target.value) as CycleDay)} disabled={busy}>
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

interface Logged {
  proposalId: string;
  title: string;
  decision: ProposalDecision;
  at: string;
}

function windowText(p: CustomEventProposal): string {
  const start = new Date(p.timeWindow.startsAt);
  const end = new Date(p.timeWindow.endsAt);
  const day = start.toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" });
  const t = (d: Date) => d.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
  return `${day} · ${t(start)}–${t(end)}`;
}

export function CustomEventQueue({ client }: { client: CycleClient }) {
  const v3 = client.v3;
  const [items, setItems] = useState<CustomEventProposal[] | string>("Loading…");
  const [notes, setNotes] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [log, setLog] = useState<Logged[]>([]);
  const request = useRef(0);

  const refresh = useCallback(async () => {
    if (!v3) return;
    const id = ++request.current;
    try {
      const value = await v3.customEvents();
      if (id === request.current) setItems(value);
    } catch (err) {
      if (id === request.current) setItems(explain(err));
    }
  }, [v3]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  if (!v3) return null;

  const decide = async (p: CustomEventProposal, decision: ProposalDecision) => {
    setBusy(p.proposalId);
    setError(null);
    try {
      const note = notes[p.proposalId]?.trim();
      const result = await v3.decideCustomEvent(p.proposalId, decision, note || undefined);
      setLog((l) => [{ proposalId: result.proposalId, title: result.title, decision, at: new Date().toISOString() }, ...l]);
      await refresh();
    } catch (err) {
      setError(explain(err));
      await refresh();
    } finally {
      setBusy(null);
    }
  };

  return (
    <section className="card cst-panel" aria-labelledby="cst-op-custom" data-testid="cst-op-custom-events">
      <h2 id="cst-op-custom" className="cst-card-title">
        <PartyPopper size={18} aria-hidden="true" /> Custom events
      </h2>
      <p className="cst-hint">
        Muse proposes an event for a cluster of repeat matches. Players see nothing until you approve, and it only runs with 3 or
        more RSVPs. Public places only.
      </p>
      {typeof items === "string" ? (
        <p className="cst-hint">{items}</p>
      ) : items.length === 0 ? (
        <p className="cst-hint">No proposals waiting.</p>
      ) : (
        <ul className="cst-proposals">
          {items.map((p) => (
            <li key={p.proposalId} className="cst-proposal">
              <div className="cst-proposal-main">
                <strong>{p.title}</strong>
                <span className="muted">{windowText(p)} · venue {p.placeId}</span>
                <span className="cst-proposal-tags">{p.why}</span>
                <span className="cst-proposal-meta">
                  <span className="cst-label">Cluster of {p.clusterSize}</span>
                  <span className="cst-label" title="Muse call metadata">
                    {p.evidence.model} · {p.evidence.callType} · {p.evidence.latencyMs} ms
                  </span>
                  {p.evidence.source !== "live" && (
                    <span className="cst-label cst-label-warn">Replay of a saved round</span>
                  )}
                </span>
              </div>
              <label className="cst-proposal-note">
                <span className="sr-only">Note for {p.title} (optional)</span>
                <input
                  type="text"
                  maxLength={200}
                  placeholder="Note (optional)"
                  value={notes[p.proposalId] ?? ""}
                  onChange={(e) => setNotes((n) => ({ ...n, [p.proposalId]: e.target.value }))}
                  disabled={busy !== null}
                />
              </label>
              <div className="cst-proposal-actions">
                <button type="button" className="button-primary" disabled={busy !== null} onClick={() => void decide(p, "approve")}>
                  <Check size={16} aria-hidden="true" /> Approve
                </button>
                <button type="button" className="button-secondary" disabled={busy !== null} onClick={() => void decide(p, "reject")}>
                  <X size={16} aria-hidden="true" /> Reject
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
      {error && (
        <p className="cst-error" role="alert">
          {error}
        </p>
      )}
      {log.length > 0 && (
        <div className="cst-proposal-log">
          <h3>Decisions this session</h3>
          <ul data-testid="cst-op-decision-log">
            {log.map((entry) => (
              <li key={`${entry.proposalId}-${entry.at}`}>
                {entry.decision === "approve" ? "Approved" : "Rejected"} “{entry.title}” ·{" "}
                {new Date(entry.at).toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" })}
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
