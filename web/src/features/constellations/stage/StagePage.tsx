/*
 * Presenter screen (D017, D019): Phone A and Phone B on the sides, what Muse and
 * the server do in the middle, and the only controls for the demo week.
 *
 * The phones appear automatically when they join (the two newest players). The
 * stage starts a demo week with the synthetic cast, fills the phones' Monday to
 * Thursday from a script, tells each presenter what to type on Friday, locks,
 * waits for Muse, and reveals. Answer text shows only for the two phones;
 * everyone else is a dot.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router";
import { MoonStar, RefreshCw, ShieldCheck, Smartphone } from "lucide-react";
import { CONSTELLATIONS_PATH } from "../daily/communities";
import { fetchStage, nextStep, redetectPhones, stageAvailable, startWeek, StageError, type Slot, type StageCall, type StagePanel, type StageView } from "./client";
import { cells, constellationMap, scatter, type Pt } from "./geometry";
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
const SLOT_COLOR: Record<Slot, string> = { A: "var(--a)", B: "var(--b)" };

// ------------------------------------------------------------------ flow
type Phase = "idle" | "prefill" | "friday" | "matching" | "ready" | "revealed";

function phaseOf(v: StageView): Phase {
  const c = v.cycle;
  if (!c || c.status === "closed") return "idle";
  if (c.status === "open") return c.currentDay < v.liveDay ? "prefill" : "friday";
  if (c.status === "revealed") return "revealed";
  return v.formation.formed ? "ready" : "matching";
}

const STEPS: { phase: Phase[]; title: string; sub: string }[] = [
  { phase: ["idle"], title: "Phones join", sub: "They appear here on their own" },
  { phase: ["prefill"], title: "Mon to Thu", sub: "Filled in for the phones" },
  { phase: ["friday"], title: "Friday", sub: "Phones answer live" },
  { phase: ["matching", "ready"], title: "Saturday", sub: "Muse finds everyone's people" },
  { phase: ["revealed"], title: "Sunday", sub: "Constellations revealed" },
];

const SAY: Record<Phase, string> = {
  idle: "Join on both phones, then start the week. 100 synthetic players come with it.",
  prefill: "Each day, 100 synthetic players answer the day's question. The phones' answers are filled in for them.",
  friday: "Both presenters type the line shown under their phone. Muse screens each answer before it is saved.",
  matching: "Muse reads every answer of the week and groups people by what they mean, not by the words they used. Code then checks every group.",
  ready: "Muse has formed the constellations and named them. Code checked every name never quotes anyone.",
  revealed: "Each phone now sees its own constellation. Different answers, different people.",
};

function buttonLabel(v: StageView, phase: Phase): string {
  if (phase === "idle") return "Start demo week";
  if (phase === "prefill") return `Next day: ${DAYS[(v.cycle?.currentDay ?? 1)]}`;
  if (phase === "friday") return "Lock the week and match";
  if (phase === "matching") return "Muse is matching…";
  if (phase === "ready") return "Reveal Sunday";
  return "Start again";
}

// ------------------------------------------------------------------ drawings
function StarMap({ seed, size, color, width = 260, height = 170 }: { seed: string; size: number; color: string; width?: number; height?: number }) {
  const map = useMemo(() => constellationMap(seed, size, width, height), [seed, size, width, height]);
  return (
    <svg className="stg-map" viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`Constellation of ${size} people`}>
      {map.edges.map(([a, b], i) => (
        <line key={i} x1={map.stars[a].x} y1={map.stars[a].y} x2={map.stars[b].x} y2={map.stars[b].y} className="stg-map-line" style={{ animationDelay: `${i * 60}ms` }} />
      ))}
      {map.stars.map((p, i) =>
        i === 0 ? (
          <g key={i}>
            <circle cx={p.x} cy={p.y} r={11} fill={color} opacity={0.25} className="stg-pulse" />
            <circle cx={p.x} cy={p.y} r={5.5} fill={color} />
          </g>
        ) : (
          <circle key={i} cx={p.x} cy={p.y} r={2.8} className="stg-map-star" style={{ animationDelay: `${i * 60}ms` }} />
        ),
      )}
    </svg>
  );
}

const SKY_W = 760;
const SKY_H = 330;

function CommunitySky({ view, phase }: { view: StageView; phase: Phase }) {
  const formed = view.formation.formed && view.constellations.length > 0;
  // A's group first, B's group last: they land in opposite corners of the sky.
  const groups = useMemo(() => {
    const list = [...view.constellations];
    const score = (c: (typeof list)[number]) => (c.slots.includes("A") ? -1 : c.slots.includes("B") ? 1 : 0);
    return list.sort((x, y) => score(x) - score(y));
  }, [view.constellations]);
  const loose = Math.min(220, Math.max(view.population.players, 2));
  const total = formed ? Math.min(220, groups.reduce((n, g) => n + g.size, 0)) : loose;
  const phones = view.panels.filter((p) => p.joined).map((p) => p.slot);

  const layout = useMemo(() => {
    const before = scatter(total, SKY_W, SKY_H);
    if (!formed) return { pos: before, slotDot: { A: 0, B: phones.includes("A") ? 1 : 0 } as Record<Slot, number>, lines: [] as [Pt, Pt][], labels: [], boxes: [] };
    const grid = cells(groups.length, SKY_W, SKY_H);
    const pos: Pt[] = [];
    const lines: [Pt, Pt][] = [];
    const labels: { x: number; y: number; name: string; slot: Slot | null }[] = [];
    const boxes: { x: number; y: number; w: number; h: number; slot: Slot }[] = [];
    const slotDot = { A: -1, B: -1 } as Record<Slot, number>;
    groups.forEach((g, k) => {
      const cell = grid[k];
      const w = cell.cw * 0.82, h = cell.ch * 0.66;
      const map = constellationMap(g.mapSeed, g.size, w, h, 0.05);
      const ox = cell.cx - w / 2, oy = cell.cy - h / 2 - cell.ch * 0.06;
      const start = pos.length;
      map.stars.forEach((p) => pos.push({ x: ox + p.x, y: oy + p.y }));
      map.edges.forEach(([a, b]) => lines.push([pos[start + a], pos[start + b]]));
      for (const s of g.slots) slotDot[s] = start;
      // Keep names (and the phones' outlines below) inside the sky at its edges.
      const labelHalf = ((shortName(g.name) ?? "").length * (g.slots[0] ? 7.2 : 6)) / 2 + 4;
      labels.push({ x: Math.min(SKY_W - labelHalf, Math.max(labelHalf, cell.cx)), y: cell.cy + cell.ch * 0.42, name: shortName(g.name) ?? "", slot: g.slots[0] ?? null });
      if (g.slots[0]) {
        const xs = map.stars.map((p) => ox + p.x), ys = map.stars.map((p) => oy + p.y);
        const half = ((shortName(g.name) ?? "").length * 7.2) / 2 + 8; // the bold name under the stars
        const x = Math.max(2, Math.min(Math.min(...xs) - 12, cell.cx - half)), y = Math.max(2, Math.min(...ys) - 12);
        const right = Math.min(SKY_W - 2, Math.max(Math.max(...xs) + 12, cell.cx + half));
        boxes.push({ x, y, w: right - x, h: cell.cy + cell.ch * 0.42 + 8 - y, slot: g.slots[0] });
      }
    });
    return { pos: pos.slice(0, total), slotDot, lines, labels, boxes };
  }, [formed, groups, total, phones]);

  const slotOf = (i: number): Slot | null => (layout.slotDot.A === i && phones.includes("A") ? "A" : layout.slotDot.B === i && phones.includes("B") ? "B" : null);
  return (
    <div className={`stg-sky is-${phase}`}>
      <div className="stg-sky-head">
        <span>
          <i className="stg-dotkey" /> one player
          {formed && (
            <>
              <i className="stg-linekey" /> one constellation
            </>
          )}
        </span>
        <span className="stg-sky-count">
          {view.population.players} players{formed ? ` · ${groups.length} constellations` : ""}
          {view.population.syntheticPlayers > 0 && <em className="stg-label">{view.population.syntheticPlayers} synthetic</em>}
        </span>
      </div>
      <svg viewBox={`0 0 ${SKY_W} ${SKY_H}`} className="stg-sky-svg" role="img" aria-label={formed ? `${groups.length} constellations` : `${view.population.players} players`}>
        {layout.boxes.map((b) => (
          <g key={b.slot} className="stg-sky-box">
            <rect x={b.x} y={b.y} width={b.w} height={b.h} rx={12} stroke={SLOT_COLOR[b.slot]} />
            <text x={b.x + 10} y={b.y + 15} fill={SLOT_COLOR[b.slot]} className="stg-sky-tag">
              {b.slot}
            </text>
          </g>
        ))}
        {formed &&
          layout.lines.map(([a, b], i) => <line key={i} x1={a.x} y1={a.y} x2={b.x} y2={b.y} className="stg-sky-line" style={{ animationDelay: `${600 + (i % 40) * 25}ms` }} />)}
        {layout.pos.map((p, i) => {
          const s = slotOf(i);
          return (
            <g key={i} className={`stg-sky-dot${s ? ` is-${s.toLowerCase()}` : ""}`} style={{ transform: `translate(${p.x}px, ${p.y}px)`, animationDelay: `${(i * 37) % 1400}ms` }}>
              {s && <circle r={10} fill={SLOT_COLOR[s]} opacity={0.25} className="stg-pulse" />}
              <circle r={s ? 5 : 2.4} fill={s ? SLOT_COLOR[s] : undefined} />
              {s && !formed && (
                <text y={-12} textAnchor="middle" className="stg-sky-tag" fill={SLOT_COLOR[s]}>
                  {s}
                </text>
              )}
            </g>
          );
        })}
        {formed &&
          layout.labels.map((l, i) => (
            <text key={i} x={l.x} y={l.y} textAnchor="middle" className={`stg-sky-name${l.slot ? ` is-${l.slot.toLowerCase()}` : ""}`}>
              {l.name}
            </text>
          ))}
      </svg>
    </div>
  );
}

// ------------------------------------------------------------------ pipeline
const NODES: { types: string[]; title: string; caption: string }[] = [
  { types: ["M1"], title: "Safety", caption: "screens each live answer" },
  { types: ["M3"], title: "Themes", caption: "what people mean" },
  { types: ["M4"], title: "Groups", caption: "people by meaning" },
  { types: ["M5"], title: "Names", caption: "one per constellation" },
  { types: ["M8"], title: "Sky", caption: "the week's headline" },
];

function Pipeline({ view, phase, fresh }: { view: StageView; phase: Phase; fresh: Set<string> }) {
  const byType = useMemo(() => {
    const map = new Map<string, StageCall[]>();
    for (const call of view.calls) map.set(call.callType, [...(map.get(call.callType) ?? []), call]);
    return map;
  }, [view.calls]);
  const answers = view.population.answersByDay.reduce((a, b) => a + b, 0);
  return (
    <ol className="stg-flow" aria-label="Muse pipeline">
      <li className={`stg-node is-input ${answers ? "is-done" : ""}`}>
        <span className="stg-node-dot">{answers}</span>
        <strong>Answers</strong>
        <small>private, this week</small>
      </li>
      {NODES.map((n) => {
        const calls = n.types.flatMap((t) => byType.get(t) ?? []);
        const last = calls[calls.length - 1];
        const isFresh = calls.some((c) => fresh.has(c.generatedAt + c.callType));
        const working = phase === "matching" && !calls.length && n.types[0] !== "M1";
        return (
          <li key={n.title} className={`stg-node ${calls.length ? "is-done" : ""} ${isFresh ? "is-fresh" : ""} ${working ? "is-working" : ""}`} data-testid={`stage-step-${n.types[0]}`}>
            <span className="stg-node-dot">{calls.length || "·"}</span>
            <strong>{n.title}</strong>
            <small>{n.caption}</small>
            {last && (
              <span className="stg-chip">
                {last.model.replace(/^muse-/, "")} · {(last.latencyMs / 1000).toFixed(1)}s{last.source !== "live" ? ` · ${last.source}` : ""}
              </span>
            )}
          </li>
        );
      })}
    </ol>
  );
}

// ------------------------------------------------------------------ phones
function Phone({ panel, view, phase }: { panel: StagePanel; view: StageView; phase: Phase }) {
  const answered = new Map(panel.answers.map((a) => [a.day, a]));
  const today = view.cycle?.status === "open" ? view.cycle.currentDay : null;
  const color = SLOT_COLOR[panel.slot];
  return (
    <section className={`stg-phone is-${panel.slot.toLowerCase()}`} aria-label={`Phone ${panel.slot}`} data-testid={`stage-phone-${panel.slot}`}>
      <header className="stg-phone-head">
        <Smartphone size={18} aria-hidden />
        <strong>Phone {panel.slot}</strong>
        <span className={`stg-dot ${panel.joined ? "is-on" : ""}`} aria-hidden />
      </header>
      <div className="stg-phone-name">{panel.joined ? panel.displayName : "Waiting for a phone"}</div>
      {!panel.joined ? (
        <div className="stg-phone-empty">
          <p>Open the site on a phone and join Facebook Space.</p>
          <p className="stg-muted">It shows up here by itself.</p>
        </div>
      ) : (
        <>
          <ol className="stg-days" aria-label="Days answered">
            {DAYS.map((d, i) => {
              const a = answered.get(i + 1);
              const cls = a ? (a.scripted ? "is-filled" : "is-live") : today === i + 1 ? "is-today" : "";
              return (
                <li key={d} className={cls} title={a ? (a.scripted ? "Filled in for the demo" : "Typed on the phone") : undefined}>
                  <span aria-hidden />
                  {d}
                </li>
              );
            })}
          </ol>
          {panel.toType && view.today && (
            <div className="stg-type" data-testid={`stage-type-${panel.slot}`}>
              <small>{DAYS[view.today.day - 1]}: {view.today.text}</small>
              <span>Type on the phone</span>
              <q>{panel.toType}</q>
            </div>
          )}
          {panel.constellation ? (
            <div className="stg-result" data-testid={`stage-result-${panel.slot}`}>
              <StarMap seed={panel.constellation.mapSeed} size={panel.constellation.size} color={color} />
              <small>{phase === "revealed" ? "Their constellation" : "Placed, not yet revealed"}</small>
              {shortName(panel.constellation.name) && <strong>{shortName(panel.constellation.name)}</strong>}
              <span>
                {panel.constellation.size} people
                {isBackup(panel.constellation.name) ? " · backup grouping" : panel.constellation.isLooseMatch ? " · loose match" : ""}
              </span>
            </div>
          ) : (
            <div className="stg-answers">
              {[...panel.answers].reverse().map((a) => (
                <article key={a.day} className={`stg-answer ${a.scripted ? "is-filled" : "is-live"}`}>
                  <small>
                    {DAYS[a.day - 1]} · {a.scripted ? "filled in" : "typed live"}
                  </small>
                  <p>{a.text}</p>
                </article>
              ))}
              {phase === "matching" && <div className="stg-shimmer">Muse is finding their people…</div>}
            </div>
          )}
        </>
      )}
    </section>
  );
}

// ------------------------------------------------------------------ page
export function StagePage() {
  const [view, setView] = useState<StageView | null>(null);
  const [error, setError] = useState<StageError | null>(null);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  const seen = useRef<Set<string> | null>(null);
  const [fresh, setFresh] = useState<Set<string>>(new Set());

  const accept = useCallback((next: StageView) => {
    const keys = next.calls.map((c) => c.generatedAt + c.callType);
    const added = seen.current ? keys.filter((k) => !seen.current!.has(k)) : [];
    seen.current = new Set(keys);
    if (added.length) {
      setFresh(new Set(added));
      window.setTimeout(() => setFresh(new Set()), 2500);
    }
    setView(next);
    setError(null);
  }, []);

  const load = useCallback(
    async (signal?: AbortSignal) => {
      try {
        accept(await fetchStage(signal));
      } catch (err) {
        if ((err as Error)?.name === "AbortError") return;
        setError(err instanceof StageError ? err : new StageError(0, "Something went wrong."));
      }
    },
    [accept],
  );

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

  const act = async (work: () => Promise<StageView>) => {
    setBusy(true);
    setNote(null);
    try {
      accept(await work());
    } catch (err) {
      setNote((err as Error).message || "That did not work.");
    } finally {
      setBusy(false);
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
            <p role="alert">{error.status === 401 ? "Join Facebook Space in this browser first." : error.message}</p>
            <Link to={CONSTELLATIONS_PATH}>Open Facebook Space</Link>
          </>
        ) : (
          <p>Loading the stage…</p>
        )}
      </main>
    );
  }

  const phase = phaseOf(view);
  const stepIndex = STEPS.findIndex((s) => s.phase.includes(phase));
  const [a, b] = view.panels;
  const run = phase === "idle" || phase === "revealed" ? startWeek : nextStep;
  const waiting = phase === "friday" ? view.panels.filter((p) => p.joined && p.toType).map((p) => `Phone ${p.slot}`) : [];
  return (
    <main className="stg" data-testid="stage">
      <header className="stg-top">
        <div className="stg-brand">
          <MoonStar size={20} aria-hidden />
          <strong>Facebook Space</strong>
          <span className="stg-muted">behind the scenes</span>
        </div>
        <ol className="stg-steps" aria-label="Demo steps">
          {STEPS.map((s, i) => (
            <li key={s.title} className={i < stepIndex ? "is-past" : i === stepIndex ? "is-now" : ""}>
              <span>{i + 1}</span>
              <div>
                <strong>{s.title}</strong>
                <small>{s.sub}</small>
              </div>
            </li>
          ))}
        </ol>
        <div className="stg-actions">
          <button type="button" className="stg-btn is-primary" disabled={busy || phase === "matching"} onClick={() => void act(run)} data-testid="stage-next">
            {busy ? "Working…" : buttonLabel(view, phase)}
          </button>
          <button type="button" className="stg-btn is-quiet" disabled={busy} onClick={() => void act(redetectPhones)} title="Pick the two newest players again">
            <RefreshCw size={14} aria-hidden /> Phones
          </button>
        </div>
      </header>
      <div className="stg-grid">
        <Phone panel={a} view={view} phase={phase} />
        <section className="stg-mid" aria-label="What Muse and the server are doing">
          <p className="stg-say" role="status">
            {SAY[phase]}
            {waiting.length > 0 && <em> Waiting for {waiting.join(" and ")}.</em>}
          </p>
          <Pipeline view={view} phase={phase} fresh={fresh} />
          <CommunitySky view={view} phase={phase} />
          {(view.themes.length > 0 || view.suppressedThemes > 0) && (
            <div className="stg-themes">
              <span className="stg-muted">Themes Muse found</span>
              {view.themes.map((t) => (
                <span key={t.label} className={`stg-tag${t.slots.length ? ` is-${t.slots.join("").toLowerCase()}` : ""}`}>
                  {t.label} · {t.count}
                </span>
              ))}
              {view.suppressedThemes > 0 && <span className="stg-tag is-hidden">{view.suppressedThemes} under 3 people, kept private</span>}
            </div>
          )}
          <p className="stg-guard">
            <ShieldCheck size={14} aria-hidden /> Muse proposes; code enforces: group sizes, one group per person, no quotes in names, and only the two phones' answers are shown here.
          </p>
        </section>
        <Phone panel={b} view={view} phase={phase} />
      </div>
      <footer className="stg-controls">
        <span className="stg-label">Demo timing</span>
        <span className="stg-label">Unofficial hackathon prototype</span>
        {(note || error) && (
          <span className="stg-note" role="alert">
            {note ?? "Connection lost. Retrying…"}
          </span>
        )}
      </footer>
    </main>
  );
}
