import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router";
import {
  ClientError,
  type CurrentCycle,
  type MuseCallEvidence,
  type Report,
  type WeeklyCycle,
} from "../daily/client";
import { getCycleClient } from "../daily/clientContext";
import { COMMUNITIES } from "../daily/communities";
import "../daily/daily.css";

const DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"];
const NEXT_STATUS: Record<string, string> = {
  open: "Lock the week (Saturday 12:00)",
  locked: "Start formation",
  forming: "Reveal constellations (Sunday 10:00)",
  revealed: "Close the week",
};

function nextStep(cycle: WeeklyCycle): string | null {
  if (cycle.status === "closed") return null;
  if (cycle.status === "open" && cycle.currentDay < 5) return `Advance to ${DAY_NAMES[cycle.currentDay]}`;
  return NEXT_STATUS[cycle.status];
}

function describe(cycle: WeeklyCycle): string {
  return cycle.status === "open" ? `Open · ${DAY_NAMES[cycle.currentDay - 1]}` : cycle.status[0].toUpperCase() + cycle.status.slice(1);
}

function text(error: unknown): string {
  return error instanceof ClientError ? `${error.code}: ${error.message}` : "Something went wrong.";
}

export default function OperatorConsole() {
  const { communityId = "" } = useParams();
  const client = getCycleClient(communityId);
  const [current, setCurrent] = useState<CurrentCycle | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [calls, setCalls] = useState<MuseCallEvidence[] | string>("Loading…");
  const [reports, setReports] = useState<Report[] | string>("Loading…");
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const request = useRef(0);

  const refresh = useCallback(async () => {
    const id = ++request.current;
    try {
      const value = await client.current();
      if (id !== request.current) return;
      setCurrent(value);
      setLoaded(true);
    } catch (err) {
      if (id === request.current) setError(text(err));
    }
    // These lists belong to other services; a failure is shown, never faked.
    client.calls().then(
      (value) => id === request.current && setCalls(value),
      (err) => id === request.current && setCalls(`Not available: ${text(err)}`),
    );
    client.reports().then(
      (value) => id === request.current && setReports(value),
      (err) => id === request.current && setReports(`Not available: ${text(err)}`),
    );
  }, [client]);

  useEffect(() => {
    void refresh();
    return () => {
      request.current++;
    };
  }, [refresh]);

  async function run(label: string, work: () => Promise<string | void>) {
    setBusy(true);
    setError(null);
    setStatus(null);
    try {
      const note = await work();
      setStatus(note ?? label);
      await refresh();
    } catch (err) {
      setError(text(err));
    } finally {
      setBusy(false);
    }
  }

  if (!COMMUNITIES[communityId]) {
    return (
      <main className="cst-page" id="main-content">
        <h1>Group not found</h1>
      </main>
    );
  }

  const cycle = current?.cycle ?? null;
  const next = cycle ? nextStep(cycle) : null;

  return (
    <main className="cst-page cst-page-wide" id="main-content">
      <header className="cst-header">
        <p className="cst-breadcrumb">
          <Link to={`/groups/${communityId}/constellations`}>Constellations</Link> · {COMMUNITIES[communityId]}
        </p>
        <h1>Operator console</h1>
        <p className="cst-chips">
          <span className="cst-chip">Simulated Facebook</span>
          <span className="cst-chip cst-chip-warn">Demo timing</span>
          {client.mode === "fixture" && (
            <span className="cst-chip cst-chip-warn" data-testid="cst-mode">
              Fixture mode · no server, no Muse
            </span>
          )}
        </p>
        <p className="cst-lede">
          Buttons move the week forward by hand. Same rules as real time: forward only, one step at a time.
        </p>
      </header>

      <section className="cst-card" aria-labelledby="cst-op-cycle">
        <h2 id="cst-op-cycle" className="cst-question">
          Weekly cycle
        </h2>
        {!loaded && <p className="cst-note">Loading…</p>}
        {loaded && !cycle && <p className="cst-note">No cycle yet. Start one to open Monday's question.</p>}
        {cycle && (
          <dl className="cst-facts">
            <div>
              <dt>State</dt>
              <dd data-testid="cst-op-state">{describe(cycle)}</dd>
            </div>
            <div>
              <dt>Week of</dt>
              <dd>{cycle.weekStart}</dd>
            </div>
            <div>
              <dt>Timing</dt>
              <dd>{cycle.demoTiming ? "Demo timing (operator)" : "Real time (clock)"}</dd>
            </div>
          </dl>
        )}
        <div className="cst-row cst-row-wrap">
          {cycle && next && (
            <button
              type="button"
              className="button-primary"
              disabled={busy}
              onClick={() => void run("Advanced.", async () => void (await client.advance(cycle.cycleId)))}
            >
              {next}
            </button>
          )}
          <button
            type="button"
            className="button-secondary"
            disabled={busy}
            onClick={() => void run("New cycle opened on Monday.", async () => void (await client.createCycle()))}
          >
            New cycle
          </button>
          {cycle && (
            <>
              <button
                type="button"
                className="button-secondary"
                disabled={busy || cycle.status !== "open"}
                onClick={() =>
                  void run("", async () => {
                    const result = await client.topUp(cycle.cycleId);
                    return `${result.label} top-up: ${result.syntheticPlayers} synthetic players, ${result.answersAdded} answers added.`;
                  })
                }
              >
                Synthetic top-up
              </button>
              <button
                type="button"
                className="button-secondary"
                disabled={busy}
                onClick={() => void run("Cycle reset to Monday. Answers cleared.", async () => void (await client.reset(cycle.cycleId)))}
              >
                Reset
              </button>
            </>
          )}
        </div>
        <p className="cst-note" role="status" data-testid="cst-op-status">
          {status}
        </p>
        {error && (
          <p className="cst-error" role="alert">
            {error}
          </p>
        )}
        <p className="cst-note">
          Synthetic top-up adds players labeled “Synthetic player”. Reset works on demo cycles only and never touches
          real sessions.
        </p>
      </section>

      <section className="cst-card" aria-labelledby="cst-op-calls">
        <h2 id="cst-op-calls" className="cst-question">
          Muse calls
        </h2>
        {typeof calls === "string" ? (
          <p className="cst-note">{calls}</p>
        ) : calls.length === 0 ? (
          <p className="cst-note">
            {client.mode === "fixture" ? "None. Fixture mode never calls Muse." : "No calls recorded yet."}
          </p>
        ) : (
          <table className="cst-table">
            <thead>
              <tr>
                <th scope="col">Call</th>
                <th scope="col">Model</th>
                <th scope="col">Source</th>
                <th scope="col">Latency</th>
              </tr>
            </thead>
            <tbody>
              {calls.map((call, index) => (
                <tr key={`${call.generatedAt}-${index}`}>
                  <td>{call.callType}</td>
                  <td>{call.model}</td>
                  <td>{call.source === "replay" ? "Replay of a saved cycle" : "Live"}</td>
                  <td>{(call.latencyMs / 1000).toFixed(1)} s</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <section className="cst-card" aria-labelledby="cst-op-reports">
        <h2 id="cst-op-reports" className="cst-question">
          Report queue
        </h2>
        {typeof reports === "string" ? (
          <p className="cst-note">{reports}</p>
        ) : reports.length === 0 ? (
          <p className="cst-note">No open reports.</p>
        ) : (
          <table className="cst-table">
            <thead>
              <tr>
                <th scope="col">Handle</th>
                <th scope="col">Reason</th>
                <th scope="col">Room</th>
                <th scope="col">When</th>
              </tr>
            </thead>
            <tbody>
              {reports.map((report) => (
                <tr key={report.reportId}>
                  <td>{report.reportedHandle}</td>
                  <td>{report.reason.replace("_", " ")}</td>
                  <td>{report.roomId}</td>
                  <td>{new Date(report.createdAt).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        <p className="cst-note">Removing a message or member happens in the chat tools.</p>
      </section>
    </main>
  );
}
