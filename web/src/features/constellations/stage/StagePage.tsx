/*
 * Presenter screen: two opted-in phones left and right, what Muse and the
 * server do in between. Operator only, live API only. Shows answer text only
 * for players who chose "Phone A" / "Phone B" on their own phone; everyone
 * else is a count or a dot.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router";
import { ArrowDown, MoonStar, ShieldCheck, Smartphone, Sparkles } from "lucide-react";
import { getCycleClient } from "../daily/clientContext";
import { CONSTELLATIONS_PATH, PLAY_COMMUNITY } from "../daily/communities";
import { fetchStage, stageAvailable, StageError, type Slot, type StageCall, type StagePanel, type StageView } from "./client";
import "./stage.css";

const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri"];
// The server marks a backup group inside its name (server/matching/models.py FALLBACK_LABEL).
// The stage says so once per place instead of repeating the label on every name.
const FALLBACK_LABEL = "Fallback grouping";
const isBackup = (name: string | null): boolean => !!name && name.includes(FALLBACK_LABEL);
function shortName(name: string | null): string | null {
  if (!name) return null;
  const short = name.replace(`(${FALLBACK_LABEL})`, "").trim();
  return short && short !== FALLBACK_LABEL ? short : null;
}
const POLL_MS = 1500;

type Step = { types: string[]; title: string; muse: string; code: string };
const STEPS: Step[] = [
  { types: ["M1"], title: "Safety check", muse: "Muse reads every answer before it is saved.", code: "Code keeps a flagged answer out of matching." },
  { types: ["M2"], title: "Follow-up", muse: "Muse asks one short question when an answer is unclear.", code: "Code blocks quotes and sensitive terms." },
  { types: ["M3"], title: "Themes", muse: "Muse reads the week and names what people mean.", code: "Code shows a theme only when 3 or more share it." },
  { types: ["M4"], title: "Constellations", muse: "Muse groups people by meaning, not by matching words.", code: "Code checks every group and places each person once." },
  { types: ["M5"], title: "Names", muse: "Muse names each constellation.", code: "Code rejects a name that quotes an answer." },
  { types: ["M8"], title: "Sky", muse: "Muse writes the headline.", code: "Code computes every number." },
];

function statusLine(view: StageView): string {
  const c = view.cycle;
  if (!c) return "No week is running";
  if (c.status === "open") return `${DAYS[c.currentDay - 1]} · answers open`;
  if (c.status === "locked") return "Saturday · answers locked";
  if (c.status === "forming") return view.formation.formed ? "Matching done · ready to reveal" : "Muse is matching";
  if (c.status === "revealed") return "Sunday · constellations revealed";
  return "Week closed";
}

function nextLabel(view: StageView): string | null {
  const c = view.cycle;
  if (!c) return "Start demo week";
  if (c.status === "open") return c.currentDay < 5 ? "Next day" : "Lock the week";
  if (c.status === "locked") return "Find people";
  if (c.status === "forming") return "Reveal";
  return null;
}

function Phone({ panel, view }: { panel: StagePanel; view: StageView }) {
  const status = view.cycle?.status;
  const answered = new Set(panel.answers.map((a) => a.day));
  const today = view.cycle?.status === "open" ? view.cycle.currentDay : 5;
  const matching = panel.joined && (status === "locked" || status === "forming") && !panel.constellation;
  return (
    <section className={`stg-phone is-${panel.slot.toLowerCase()}`} aria-label={`Phone ${panel.slot}`} data-testid={`stage-phone-${panel.slot}`}>
      <header className="stg-phone-head">
        <Smartphone size={18} aria-hidden />
        <strong>Phone {panel.slot}</strong>
        <span className={`stg-dot ${panel.joined ? "is-on" : ""}`} aria-hidden />
        <span className="stg-muted">{panel.joined ? "on stage" : "not connected"}</span>
      </header>
      {!panel.joined ? (
        <div className="stg-phone-empty">
          <p>On the phone, open</p>
          <p className="stg-path">Facebook Space → Privacy → Demo screen</p>
          <p>
            and choose <strong>Phone {panel.slot}</strong>.
          </p>
        </div>
      ) : (
        <>
          <ol className="stg-days" aria-label="Days answered">
            {DAYS.map((d, i) => (
              <li key={d} className={answered.has(i + 1) ? "is-done" : i + 1 === today && status === "open" ? "is-today" : ""}>
                <span aria-hidden />
                {d}
              </li>
            ))}
          </ol>
          <div className="stg-answers">
            {panel.answers.length === 0 && <p className="stg-muted">No answer yet.</p>}
            {panel.answers.map((a) => (
              <article key={a.day} className="stg-answer">
                <small>{DAYS[a.day - 1]}</small>
                <p>{a.text}</p>
              </article>
            ))}
          </div>
          <footer className="stg-phone-foot">
            {panel.constellation ? (
              <div className="stg-result" data-testid={`stage-result-${panel.slot}`}>
                <MoonStar size={18} aria-hidden />
                <div>
                  <small>{status === "revealed" ? "Their constellation" : "Placed, not yet revealed"}</small>
                  {/* Names that fail the privacy check arrive as null; leave the line out instead of a placeholder. */}
                  {shortName(panel.constellation.name) && <strong>{shortName(panel.constellation.name)}</strong>}
                  <span>
                    {panel.constellation.size} people
                    {isBackup(panel.constellation.name) ? " · backup grouping" : panel.constellation.isLooseMatch ? " · loose match" : ""}
                  </span>
                </div>
              </div>
            ) : matching ? (
              <div className="stg-shimmer">Muse is finding their people…</div>
            ) : status === "revealed" ? (
              <p className="stg-muted">Not placed this week.</p>
            ) : (
              <p className="stg-muted">Shown here because this player turned it on.</p>
            )}
          </footer>
        </>
      )}
    </section>
  );
}

function Chip({ call }: { call: StageCall }) {
  return (
    <span className="stg-chip">
      {call.callType} · {call.model} · {Math.round(call.latencyMs)} ms{call.source !== "live" ? ` · ${call.source}` : ""}
    </span>
  );
}

function Pipeline({ view, fresh }: { view: StageView; fresh: Set<string> }) {
  const byType = useMemo(() => {
    const map = new Map<string, StageCall[]>();
    for (const call of view.calls) map.set(call.callType, [...(map.get(call.callType) ?? []), call]);
    return map;
  }, [view.calls]);
  const maxDay = Math.max(1, ...view.population.answersByDay);
  const slotOf = (slots: Slot[]) => (slots.length ? ` is-${slots.join("").toLowerCase()}` : "");
  return (
    <section className="stg-mid" aria-label="What the server and Muse are doing">
      <div className="stg-pop">
        <div>
          <strong>{view.population.players}</strong>
          <span>players answering</span>
          {view.population.syntheticPlayers > 0 && <em className="stg-label">{view.population.syntheticPlayers} are synthetic players</em>}
        </div>
        <ol className="stg-bars" aria-label="Answers per day">
          {view.population.answersByDay.map((n, i) => (
            <li key={DAYS[i]}>
              <span style={{ height: `${Math.round((n / maxDay) * 100)}%` }} />
              <small>
                {DAYS[i]} {n}
              </small>
            </li>
          ))}
        </ol>
      </div>
      <ArrowDown className="stg-arrow" size={18} aria-hidden />
      <ol className="stg-steps">
        {STEPS.map((step) => {
          const calls = step.types.flatMap((t) => byType.get(t) ?? []);
          const last = calls[calls.length - 1];
          const isFresh = calls.some((c) => fresh.has(c.generatedAt + c.callType));
          return (
            <li key={step.title} className={`stg-step ${calls.length ? "is-done" : ""} ${isFresh ? "is-fresh" : ""}`} data-testid={`stage-step-${step.types[0]}`}>
              <div className="stg-step-head">
                <Sparkles size={16} aria-hidden />
                <strong>{step.title}</strong>
                <span className="stg-count">{calls.length ? `${calls.length} call${calls.length === 1 ? "" : "s"}` : "waiting"}</span>
              </div>
              <p className="stg-muse">{step.muse}</p>
              <p className="stg-code">
                <ShieldCheck size={14} aria-hidden /> {step.code}
              </p>
              {last && <Chip call={last} />}
              {step.types[0] === "M3" && (view.themes.length > 0 || view.suppressedThemes > 0) && (
                <div className="stg-tags">
                  {view.themes.map((t) => (
                    <span key={t.label} className={`stg-tag${slotOf(t.slots)}`}>
                      {t.label} · {t.count}
                    </span>
                  ))}
                  {view.suppressedThemes > 0 && <span className="stg-tag is-hidden">{view.suppressedThemes} smaller themes kept private</span>}
                </div>
              )}
              {step.types[0] === "M4" && view.constellations.length > 0 && (
                <div className="stg-groups" aria-label={`${view.constellations.length} constellations`}>
                  {view.constellations.map((c, i) => (
                    <span key={i} className={`stg-group${slotOf(c.slots)}`} title={`${c.size} people`}>
                      {Array.from({ length: c.size }, (_, j) => (
                        <i key={j} className={j < c.slots.length ? `is-${c.slots[j].toLowerCase()}` : ""} />
                      ))}
                    </span>
                  ))}
                </div>
              )}
              {step.types[0] === "M5" && view.constellations.some((c) => isBackup(c.name)) && (
                <p className="stg-note" data-testid="stage-backup-note">
                  Backup grouping: Muse's grouping was not used this time. Code grouped people by shared keywords and named the groups.
                </p>
              )}
              {step.types[0] === "M5" && view.constellations.some((c) => shortName(c.name)) && (
                <div className="stg-tags">
                  {view.constellations
                    .filter((c) => shortName(c.name))
                    .map((c, i) => (
                      <span key={i} className={`stg-tag${slotOf(c.slots)}`}>
                        {shortName(c.name)}
                      </span>
                    ))}
                </div>
              )}
            </li>
          );
        })}
      </ol>
    </section>
  );
}

export function StagePage() {
  const [view, setView] = useState<StageView | null>(null);
  const [error, setError] = useState<StageError | null>(null);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  const seen = useRef<Set<string> | null>(null);
  const [fresh, setFresh] = useState<Set<string>>(new Set());

  const load = useCallback(async (signal?: AbortSignal) => {
    try {
      const next = await fetchStage(signal);
      const keys = next.calls.map((c) => c.generatedAt + c.callType);
      const added = seen.current ? keys.filter((k) => !seen.current!.has(k)) : [];
      seen.current = new Set(keys);
      if (added.length) {
        setFresh(new Set(added));
        window.setTimeout(() => setFresh(new Set()), 2500);
      }
      setView(next);
      setError(null);
    } catch (err) {
      if ((err as Error)?.name === "AbortError") return;
      setError(err instanceof StageError ? err : new StageError(0, "Something went wrong."));
    }
  }, []);

  useEffect(() => {
    if (!stageAvailable) return;
    const ctl = new AbortController();
    void load(ctl.signal);
    const timer = window.setInterval(() => void load(ctl.signal), POLL_MS);
    return () => {
      ctl.abort();
      window.clearInterval(timer);
    };
  }, [load]);

  const act = async (work: () => Promise<unknown>) => {
    setBusy(true);
    setNote(null);
    try {
      await work();
    } catch (err) {
      setNote((err as Error).message || "That did not work.");
    } finally {
      setBusy(false);
      void load();
    }
  };

  if (!stageAvailable) {
    return (
      <main className="stg stg-center">
        <p>The stage view needs the live server. It is not available in fixture mode.</p>
        <Link to={CONSTELLATIONS_PATH}>Back to Facebook Space</Link>
      </main>
    );
  }
  if (!view) {
    return (
      <main className="stg stg-center">
        {error ? (
          <>
            <p role="alert">{error.status === 401 ? "Join Facebook Space in this browser first." : error.status === 403 ? "This browser's player is not an operator." : error.message}</p>
            <Link to={CONSTELLATIONS_PATH}>Open Facebook Space</Link>
          </>
        ) : (
          <p>Loading the stage…</p>
        )}
      </main>
    );
  }

  const client = getCycleClient(PLAY_COMMUNITY);
  const cycle = view.cycle;
  const next = nextLabel(view);
  const waitingOnMuse = cycle?.status === "forming" && !view.formation.formed;
  const [a, b] = view.panels;
  return (
    <main className="stg" data-testid="stage">
      <header className="stg-top">
        <div className="stg-brand">
          <MoonStar size={20} aria-hidden />
          <strong>Facebook Space</strong>
          <span className="stg-muted">behind the scenes</span>
        </div>
        <div className="stg-status" role="status">
          {statusLine(view)}
        </div>
        <div className="stg-labels">
          <span className="stg-label">Demo timing</span>
          <span className="stg-label">Unofficial hackathon prototype</span>
        </div>
      </header>
      <div className="stg-grid">
        <Phone panel={a} view={view} />
        <Pipeline view={view} fresh={fresh} />
        <Phone panel={b} view={view} />
      </div>
      <footer className="stg-controls">
        {next && (
          <button
            type="button"
            className="stg-btn is-primary"
            disabled={busy || waitingOnMuse}
            onClick={() => void act(() => (cycle ? client.advance(cycle.cycleId) : client.createCycle()))}
            data-testid="stage-next"
          >
            {waitingOnMuse ? "Muse is matching…" : next}
          </button>
        )}
        {cycle?.status === "open" && (
          <button type="button" className="stg-btn" disabled={busy} onClick={() => void act(() => client.topUp(cycle.cycleId))} data-testid="stage-topup">
            Add synthetic players
          </button>
        )}
        {cycle && (cycle.status === "revealed" || cycle.status === "closed") && (
          <button type="button" className="stg-btn" disabled={busy} onClick={() => void act(() => client.reset(cycle.cycleId))}>
            Restart week
          </button>
        )}
        {(note || error) && (
          <span className="stg-note" role="alert">
            {note ?? "Connection lost. Retrying…"}
          </span>
        )}
        <span className="stg-muted stg-right">Answer text appears only for the two phones that turned it on. Everyone else is a count.</span>
      </footer>
    </main>
  );
}
