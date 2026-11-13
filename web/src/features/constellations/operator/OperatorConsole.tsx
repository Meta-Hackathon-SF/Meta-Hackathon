import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router";
import LeftSidebar from "../../../components/layout/LeftSidebar";
import { Activity, CalendarDays, Flag, MapPin, RotateCcw, Sparkles, UserPlus, Users } from "lucide-react";
import {
  ClientError,
  type CurrentCycle,
  type FormationDebugProps,
  type MuseCallEvidence,
  type Report,
  type WeeklyCycle,
} from "../daily/client";
import { getCycleClient } from "../daily/clientContext";
import { getPrivacyClient, usePrivacySession } from "../privacy";
import { CONSTELLATIONS_PATH, FEATURE_NAME, PLAY_COMMUNITY } from "../daily/communities";
import { FormationDebug } from "../formation";
import { OperatorNudgePanel } from "../nudges";
import { CloseDayControl } from "./V3Panels";
import "../daily/daily.css";

const DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"];
const STEPS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Lock", "Form", "Reveal", "Close"];
const STATUS_STEP: Record<string, number> = { locked: 5, forming: 6, revealed: 7, closed: 8 };

const NEXT: Record<string, { label: string; effect: string }> = {
  open: {
    label: "Lock the week (Saturday 12:00)",
    effect: "Freezes every answer. Catch-up closes.",
  },
  locked: { label: "Start formation", effect: "Muse groups everyone by meaning; code checks every rule." },
  forming: {
    label: "Reveal constellations (Sunday 10:00)",
    effect: "Players see their constellation and its anonymous chat opens.",
  },
  revealed: { label: "Close the week", effect: "Ends the week. Chats close at the next lock." },
};

function nextStep(cycle: WeeklyCycle): { label: string; effect: string } | null {
  if (cycle.status === "closed") return null;
  if (cycle.status === "open" && cycle.currentDay < 5)
    return {
      label: `Advance to ${DAY_NAMES[cycle.currentDay]}`,
      effect: `Releases ${DAY_NAMES[cycle.currentDay]}'s question. ${DAY_NAMES[cycle.currentDay - 1]} becomes a catch-up day.`,
    };
  return NEXT[cycle.status];
}

function describe(cycle: WeeklyCycle): string {
  return cycle.status === "open"
    ? `Open · ${DAY_NAMES[cycle.currentDay - 1]}`
    : cycle.status[0].toUpperCase() + cycle.status.slice(1);
}

function stepOf(cycle: WeeklyCycle): number {
  return cycle.status === "open" ? cycle.currentDay - 1 : STATUS_STEP[cycle.status];
}

function text(error: unknown): string {
  if (error instanceof ClientError) {
    if (error.code === "UNAUTHENTICATED") return `Sign in from the ${FEATURE_NAME} page first.`;
    if (error.code === "FORBIDDEN") return "This account isn't an operator for this Group.";
    return `${error.code}: ${error.message}`;
  }
  return "Something went wrong.";
}

function shortTime(iso: string): string {
  return new Date(iso).toLocaleString(undefined, { weekday: "short", hour: "numeric", minute: "2-digit" });
}

function median(values: number[]): number {
  const sorted = [...values].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
}

type Confirm = "reset" | "new" | null;

export default function OperatorEntry() {
  const privacy = getPrivacyClient();
  const { state, set } = usePrivacySession(privacy, PLAY_COMMUNITY);
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  if (privacy.mode === "fixture") return <OperatorConsole />;
  if (state.status === "ready" && state.view.isOperator) return <OperatorConsole />;
  return <main className="cst-page" id="main-content">
    <h1>Demo host sign in</h1>
    {state.status === "loading" ? <p>Checking session…</p> :
      state.status !== "ready" ? <p>First <Link to="/space">join Facebook Space</Link> and accept the required consent.</p> :
      <form onSubmit={(event) => {
        event.preventDefault();
        setBusy(true);
        setError("");
        void privacy.hostLogin(password).then((view) => { setPassword(""); set(view); }, (err: unknown) => {
          setPassword("");
          setError(err instanceof Error ? err.message : "Unable to sign in.");
        }).finally(() => setBusy(false));
      }}>
        <label htmlFor="demo-host-password">Demo host password</label>
        <input id="demo-host-password" type="password" autoComplete="current-password" required maxLength={1024} value={password} onChange={(event) => setPassword(event.target.value)} />
        <button type="submit" disabled={busy}>Sign in as demo host</button>
        {error && <p role="alert">{error}</p>}
      </form>}
  </main>;
}

function OperatorConsole() {
  const communityId = PLAY_COMMUNITY;
  const client = getCycleClient(communityId);
  const [current, setCurrent] = useState<CurrentCycle | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [calls, setCalls] = useState<MuseCallEvidence[] | string>("Loading…");
  const [reports, setReports] = useState<Report[] | string>("Loading…");
  const [formation, setFormation] = useState<FormationDebugProps | string | null>(null);
  const [myRoom, setMyRoom] = useState<string | null>(null);
  const [nudgeRoom, setNudgeRoom] = useState<string>("");
  const [busy, setBusy] = useState(false);
  const [confirm, setConfirm] = useState<Confirm>(null);
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
      if (value && value.cycle.status !== "open")
        client.formationDebug(value.cycle.cycleId).then(
          (debug) => id === request.current && setFormation(debug),
          (err) => id === request.current && setFormation(`Not available: ${text(err)}`),
        );
      else setFormation(null);
      if (value && value.cycle.status === "revealed")
        client.myRoomId(value.cycle.cycleId).then(
          (roomId) => id === request.current && setMyRoom(roomId),
          () => id === request.current && setMyRoom(null),
        );
      else setMyRoom(null);
    } catch (err) {
      if (id === request.current) {
        setLoaded(true);
        setError(text(err));
      }
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
    const counter = request;
    void refresh();
    return () => {
      counter.current++;
    };
  }, [refresh]);

  async function run(label: string, work: () => Promise<string | void>) {
    setBusy(true);
    setError(null);
    setStatus(null);
    setConfirm(null);
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


  const cycle = current?.cycle ?? null;
  const next = cycle ? nextStep(cycle) : null;
  const step = cycle ? stepOf(cycle) : -1;
  const startNew = () =>
    void run("New week opened on Monday.", async () => void (await client.createCycle()));

  return (
    <div className="secondary-layout cst-op-layout">
    <LeftSidebar />
    <main className="cst-page cst-op" id="main-content">
      <header className="card cst-group-header">
        <div className="cst-group-id">
          <p className="cst-crumb">
            <Link to={CONSTELLATIONS_PATH}>{FEATURE_NAME}</Link>
          </p>
          <h1>Operator console</h1>
          <p className="muted">Run the week by hand for the demo. Same rules as real time: forward only, one step at a time.</p>
          <p className="cst-labels">
            <span className="cst-label">Simulated Facebook</span>
            <span className="cst-label cst-label-warn">Demo timing</span>
            {client.mode === "fixture" && (
              <span className="cst-label cst-label-warn" data-testid="cst-mode">
                Fixture mode · no server, no Muse
              </span>
            )}
          </p>
        </div>
      </header>

      <section className="card cst-panel" aria-labelledby="cst-op-cycle">
        <div className="cst-op-head">
          <h2 id="cst-op-cycle">
            <CalendarDays size={18} aria-hidden="true" /> This week
          </h2>
          {cycle && (
            <span className={`cst-pill is-${cycle.status}`} data-testid="cst-op-state">
              {describe(cycle)}
            </span>
          )}
        </div>

        {!loaded && <div className="cst-skel cst-skel-steps" role="status" aria-label="Loading" />}
        {loaded && !cycle && (
          <p className="cst-hint">No week yet. Start one to release Monday's question to every player.</p>
        )}

        {cycle && (
          <>
            <ol className="cst-steps" aria-label="Week progress">
              {STEPS.map((label, index) => (
                <li
                  key={label}
                  className={`cst-step ${index < step ? "is-done" : index === step ? "is-current" : "is-upcoming"}${index === 5 ? " is-weekend" : ""}`}
                  aria-current={index === step ? "step" : undefined}
                >
                  <span className="cst-step-dot" aria-hidden="true" />
                  <span className="cst-step-label">{label}</span>
                </li>
              ))}
            </ol>
            <dl className="cst-facts">
              <div>
                <dt>Week of</dt>
                <dd>{cycle.weekStart}</dd>
              </div>
              <div>
                <dt>Locks</dt>
                <dd>{shortTime(cycle.locksAt)}</dd>
              </div>
              <div>
                <dt>Reveals</dt>
                <dd>{shortTime(cycle.revealsAt)}</dd>
              </div>
              <div>
                <dt>Timing</dt>
                <dd>{cycle.demoTiming ? "Demo (operator)" : "Real time (clock)"}</dd>
              </div>
            </dl>
          </>
        )}

        {cycle && next && (
          <div className="cst-op-next">
            <button
              type="button"
              className="button-primary cst-op-advance"
              disabled={busy}
              onClick={() => void run("Advanced.", async () => void (await client.advance(cycle.cycleId)))}
            >
              {next.label}
            </button>
            <p className="cst-hint">{next.effect}</p>
          </div>
        )}

        {cycle && <CloseDayControl client={client} cycle={cycle} onDone={() => void refresh()} />}

        <p className="cst-op-status" role="status" data-testid="cst-op-status">
          {status}
        </p>
        {error && (
          <p className="cst-error" role="alert">
            {error}
          </p>
        )}

        <div className="cst-op-tools">
          {confirm === "new" ? (
            <div className="cst-confirm" role="group" aria-label="Confirm new week">
              <span>Start a new week? Players move to its Monday question.</span>
              <button type="button" className="cst-danger" onClick={startNew} disabled={busy}>
                Start new week
              </button>
              <button type="button" className="cst-text-button" onClick={() => setConfirm(null)}>
                Cancel
              </button>
            </div>
          ) : confirm === "reset" && cycle ? (
            <div className="cst-confirm" role="group" aria-label="Confirm reset">
              <span>Reset this demo week to Monday? Answers are cleared.</span>
              <button
                type="button"
                className="cst-danger"
                disabled={busy}
                onClick={() =>
                  void run("Week reset to Monday. Answers cleared.", async () => void (await client.reset(cycle.cycleId)))
                }
              >
                Reset week
              </button>
              <button type="button" className="cst-text-button" onClick={() => setConfirm(null)}>
                Cancel
              </button>
            </div>
          ) : (
            <>
              <button
                type="button"
                className="button-secondary"
                disabled={busy}
                onClick={() => (cycle && cycle.status !== "closed" ? setConfirm("new") : startNew())}
              >
                <CalendarDays size={16} aria-hidden="true" /> New cycle
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
                    <UserPlus size={16} aria-hidden="true" /> Synthetic top-up
                  </button>
                  <button
                    type="button"
                    className="button-secondary"
                    disabled={busy}
                    onClick={() => setConfirm("reset")}
                  >
                    <RotateCcw size={16} aria-hidden="true" /> Reset
                  </button>
                </>
              )}
            </>
          )}
        </div>
        <p className="cst-hint">
          Synthetic top-up adds players labeled “Synthetic player”. Reset works on demo weeks only and never touches
          real sessions.
        </p>
      </section>

      <div className="cst-op-grid">
        <section className="card cst-panel" aria-labelledby="cst-op-calls">
          <h2 id="cst-op-calls" className="cst-card-title">
            <Sparkles size={18} aria-hidden="true" /> Muse calls
          </h2>
          {typeof calls === "string" ? (
            <p className="cst-hint">{calls}</p>
          ) : calls.length === 0 ? (
            <p className="cst-hint">
              {client.mode === "fixture" ? "None. Fixture mode never calls Muse." : "No calls recorded yet."}
            </p>
          ) : (
            <>
              <dl className="cst-stats">
                <div>
                  <dt>Calls</dt>
                  <dd>{calls.length}</dd>
                </div>
                <div>
                  <dt>Live</dt>
                  <dd>{calls.filter((c) => c.source === "live").length}</dd>
                </div>
                <div>
                  <dt>Median latency</dt>
                  <dd>{(median(calls.map((c) => c.latencyMs)) / 1000).toFixed(1)} s</dd>
                </div>
              </dl>
              <div className="cst-table-wrap">
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
                        <td>
                          {call.source === "replay" ? (
                            <span className="cst-label cst-label-warn">Replay of a saved cycle</span>
                          ) : (
                            "Live"
                          )}
                        </td>
                        <td className="cst-num">{(call.latencyMs / 1000).toFixed(1)} s</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </section>

        <section className="card cst-panel" aria-labelledby="cst-op-reports">
          <h2 id="cst-op-reports" className="cst-card-title">
            <Flag size={18} aria-hidden="true" /> Report queue
          </h2>
          {typeof reports === "string" ? (
            <p className="cst-hint">{reports}</p>
          ) : reports.length === 0 ? (
            <p className="cst-hint">No open reports.</p>
          ) : (
            <div className="cst-table-wrap">
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
            </div>
          )}
          <p className="cst-hint">Removing a message or member happens in the chat tools.</p>
        </section>
      </div>

      <NudgeSection
        client={client}
        revealed={cycle?.status === "revealed"}
        rooms={roomChoices(myRoom, reports)}
        selected={nudgeRoom}
        onSelect={setNudgeRoom}
      />

      <section className="card cst-panel" aria-labelledby="cst-op-formation">
        <h2 id="cst-op-formation" className="cst-card-title">
          <Users size={18} aria-hidden="true" /> Formation
        </h2>
        {typeof formation === "string" ? (
          <p className="cst-hint">{formation}</p>
        ) : formation ? (
          <FormationDebug {...formation} />
        ) : (
          <p className="cst-hint" data-testid="cst-op-formation-empty">
            <Activity size={14} aria-hidden="true" />{" "}
            {client.mode === "fixture"
              ? "Formation runs on the server. Fixture mode has no formation result."
              : cycle && cycle.status !== "open"
                ? "No formation result yet."
                : "Formation runs when the week locks."}
          </p>
        )}
      </section>
    </main>
    </div>
  );
}

/** Rooms the operator can nudge: their own room (GET /cycles/:id/room), then rooms seen in the report queue. */
function roomChoices(myRoom: string | null, reports: Report[] | string): { roomId: string; label: string }[] {
  const out: { roomId: string; label: string }[] = [];
  if (myRoom) out.push({ roomId: myRoom, label: `Your room · ${myRoom}` });
  if (typeof reports !== "string")
    for (const report of reports)
      if (!out.some((r) => r.roomId === report.roomId)) out.push({ roomId: report.roomId, label: `Reported room · ${report.roomId}` });
  return out;
}

function NudgeSection({
  client,
  revealed,
  rooms,
  selected,
  onSelect,
}: {
  client: ReturnType<typeof getCycleClient>;
  revealed: boolean;
  rooms: { roomId: string; label: string }[];
  selected: string;
  onSelect: (roomId: string) => void;
}) {
  const roomId = rooms.some((r) => r.roomId === selected) ? selected : (rooms[0]?.roomId ?? "");
  return (
    <section className="card cst-panel" aria-labelledby="cst-op-nudge" data-testid="cst-op-nudge">
      <h2 id="cst-op-nudge" className="cst-card-title">
        <MapPin size={18} aria-hidden="true" /> Nudge a room
      </h2>
      {!revealed ? (
        <p className="cst-hint">Nudges go to a constellation's chat room, so they open after Sunday's reveal.</p>
      ) : rooms.length === 0 ? (
        <p className="cst-hint">No room found yet. Join the week as a player to get a room to nudge.</p>
      ) : (
        <>
          <label className="cst-op-field">
            <span>Room</span>
            <select value={roomId} onChange={(event) => onSelect(event.target.value)}>
              {rooms.map((room) => (
                <option key={room.roomId} value={room.roomId}>
                  {room.label}
                </option>
              ))}
            </select>
          </label>
          <OperatorNudgePanel roomId={roomId} request={client.nudge} />
          {client.mode === "fixture" && (
            <p className="cst-hint">Fixture mode: the nudge is a saved result, labeled as a replay. Nothing is posted.</p>
          )}
        </>
      )}
    </section>
  );
}
