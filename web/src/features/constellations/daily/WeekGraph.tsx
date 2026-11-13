/*
 * "Your week" as a node graph, in the spirit of Obsidian's graph view:
 * you at the centre, one node per question day, Sunday's reveal at the edge.
 * Nodes settle with a tiny force simulation, can be dragged, and hovering or
 * focusing a node dims everything that isn't connected to it.
 * Only the player's own week is drawn. Nothing about other players appears.
 */
import { useEffect, useId, useMemo, useRef, useState, type PointerEvent as ReactPointerEvent } from "react";
import type { DailyAnswer, WeeklyCycle } from "./client";
import { DAY_NAMES } from "./useDaily";

export type DayState = "answered" | "caught-up" | "today" | "missed" | "upcoming";
const STATE_LABEL: Record<DayState, string> = {
  answered: "Answered",
  "caught-up": "Caught up",
  today: "Today",
  missed: "Missed",
  upcoming: "Upcoming",
};

export function dayStates(cycle: WeeklyCycle, answers: DailyAnswer[]): DayState[] {
  const open = cycle.status === "open";
  return [1, 2, 3, 4, 5].map((day) => {
    const answer = answers.find((a) => a.day === day);
    if (answer) return answer.isCatchUp ? "caught-up" : "answered";
    if (open && day === cycle.currentDay) return "today";
    if (open && day > cycle.currentDay) return "upcoming";
    return "missed";
  });
}

interface GNode {
  id: string;
  kind: "you" | "day" | "reveal";
  day?: number;
  state?: DayState;
  label: string;
  sub: string;
  r: number;
  x: number;
  y: number;
  vx: number;
  vy: number;
  pinned: boolean;
}
interface GEdge {
  a: string;
  b: string;
  kind: "spoke" | "spoke-on" | "chain" | "streak" | "future";
}

const W = 600;

function radius(kind: GNode["kind"], state: DayState | undefined, compact: boolean): number {
  const k = compact ? 0.8 : 1;
  if (kind === "you") return 18 * k;
  if (kind === "reveal") return 11 * k;
  switch (state) {
    case "answered":
      return 11 * k;
    case "caught-up":
    case "today":
      return 10 * k;
    case "missed":
      return 7 * k;
    default:
      return 6 * k;
  }
}

function build(states: DayState[], revealed: boolean, open: boolean, height: number, compact: boolean) {
  const cx = W / 2;
  const cy = height / 2;
  const nodes: GNode[] = [
    { id: "you", kind: "you", label: "You", sub: "", r: radius("you", undefined, compact), x: cx, y: cy, vx: 0, vy: 0, pinned: false },
  ];
  states.forEach((state, i) => {
    // Start on an arc so the settled shape is stable from render to render.
    const angle = Math.PI * (0.92 + (i / 4) * 1.16);
    nodes.push({
      id: `d${i + 1}`,
      kind: "day",
      day: i + 1,
      state,
      label: DAY_NAMES[i].slice(0, 3),
      sub: state === "missed" && open ? "Catch up" : STATE_LABEL[state],
      r: radius("day", state, compact),
      x: cx + Math.cos(angle) * 150,
      y: cy + Math.sin(angle) * (height * 0.36),
      vx: 0,
      vy: 0,
      pinned: false,
    });
  });
  nodes.push({
    id: "sun",
    kind: "reveal",
    label: "Sun",
    sub: revealed ? "Revealed" : "Reveal",
    r: radius("reveal", undefined, compact),
    x: cx + 210,
    y: cy + 10,
    vx: 0,
    vy: 0,
    pinned: false,
  });

  const edges: GEdge[] = [];
  states.forEach((state, i) => {
    const on = state === "answered" || state === "caught-up";
    edges.push({ a: "you", b: `d${i + 1}`, kind: on ? "spoke-on" : "spoke" });
    if (i < 4) {
      const streak = state === "answered" && states[i + 1] === "answered";
      edges.push({ a: `d${i + 1}`, b: `d${i + 2}`, kind: streak ? "streak" : "chain" });
    }
  });
  edges.push({ a: "d5", b: "sun", kind: "future" });
  edges.push({ a: "you", b: "sun", kind: "future" });
  return { nodes, edges };
}

function step(nodes: GNode[], edges: GEdge[], height: number, alpha: number) {
  const byId = new Map(nodes.map((n) => [n.id, n]));
  const cx = W / 2;
  const cy = height / 2;
  for (let i = 0; i < nodes.length; i++) {
    for (let j = i + 1; j < nodes.length; j++) {
      const a = nodes[i];
      const b = nodes[j];
      let dx = b.x - a.x;
      let dy = b.y - a.y;
      let d2 = dx * dx + dy * dy;
      if (d2 < 1) {
        dx = (i - j) * 0.5;
        dy = 0.5;
        d2 = 1;
      }
      const force = (9000 / d2) * alpha;
      const d = Math.sqrt(d2);
      a.vx -= (dx / d) * force;
      a.vy -= (dy / d) * force;
      b.vx += (dx / d) * force;
      b.vy += (dy / d) * force;
    }
  }
  for (const edge of edges) {
    const a = byId.get(edge.a)!;
    const b = byId.get(edge.b)!;
    const dx = b.x - a.x;
    const dy = b.y - a.y;
    const d = Math.max(1, Math.hypot(dx, dy));
    const rest = edge.kind === "chain" || edge.kind === "streak" ? 118 : edge.kind === "future" ? 190 : 150;
    const pull = (d - rest) * 0.04 * alpha;
    a.vx += (dx / d) * pull;
    a.vy += (dy / d) * pull;
    b.vx -= (dx / d) * pull;
    b.vy -= (dy / d) * pull;
  }
  for (const n of nodes) {
    n.vx += (cx - n.x) * 0.006 * alpha;
    n.vy += (cy - n.y) * 0.016 * alpha;
    if (n.pinned) {
      n.vx = 0;
      n.vy = 0;
      continue;
    }
    n.vx *= 0.82;
    n.vy *= 0.82;
    n.x = Math.min(W - n.r - 26, Math.max(n.r + 26, n.x + n.vx));
    n.y = Math.min(height - n.r - 36, Math.max(n.r + 12, n.y + n.vy)); // room for two label lines
  }
}

const reducedMotion = () =>
  typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

export default function WeekGraph({
  cycle,
  answers,
  avatar,
  variant = "light",
  onSelectDay,
}: {
  cycle: WeeklyCycle;
  answers: DailyAnswer[];
  avatar?: string;
  /** "light": interactive card graph. "dark": decorative, behind a colored panel. */
  variant?: "light" | "dark";
  onSelectDay?: (day: number) => void;
}) {
  const compact = variant === "dark";
  const height = compact ? 220 : 280;
  const states = useMemo(() => dayStates(cycle, answers), [cycle, answers]);
  const key = `${states.join(",")}|${cycle.status}`;
  const graph = useRef<{ key: string; nodes: GNode[]; edges: GEdge[] } | null>(null);
  if (!graph.current || graph.current.key !== key) {
    const previous = graph.current?.nodes;
    const built = build(
      states,
      cycle.status === "revealed" || cycle.status === "closed",
      cycle.status === "open",
      height,
      compact,
    );
    // Keep positions across updates so the graph doesn't jump when you answer.
    if (previous) for (const n of built.nodes) Object.assign(n, { x: previous.find((p) => p.id === n.id)?.x ?? n.x, y: previous.find((p) => p.id === n.id)?.y ?? n.y });
    else for (let i = 0; i < 260; i++) step(built.nodes, built.edges, height, 1);
    graph.current = { key, ...built };
  }
  const [, setFrame] = useState(0);
  const [hover, setHover] = useState<string | null>(null);
  const alpha = useRef(previousAlpha(graph.current));
  const svg = useRef<SVGSVGElement | null>(null);
  const drag = useRef<string | null>(null);
  const clipId = `cst-you-${useId().replace(/:/g, "")}`;

  useEffect(() => {
    if (reducedMotion()) return;
    alpha.current = Math.max(alpha.current, 0.6);
    let raf = 0;
    const tick = () => {
      const g = graph.current!;
      step(g.nodes, g.edges, height, alpha.current);
      alpha.current *= drag.current ? 1 : 0.985;
      setFrame((f) => f + 1);
      if (alpha.current > 0.02 || drag.current) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [key, height]);

  const g = graph.current;
  const byId = new Map(g.nodes.map((n) => [n.id, n]));
  const neighbors = new Set<string>();
  if (hover) {
    neighbors.add(hover);
    for (const e of g.edges) {
      if (e.a === hover) neighbors.add(e.b);
      if (e.b === hover) neighbors.add(e.a);
    }
  }
  const dim = (id: string) => hover !== null && !neighbors.has(id);

  const toSvg = (event: ReactPointerEvent) => {
    const matrix = svg.current?.getScreenCTM();
    if (!matrix) return null;
    const point = new DOMPoint(event.clientX, event.clientY).matrixTransform(matrix.inverse());
    return { x: point.x, y: point.y };
  };
  const interactive = variant === "light";

  return (
    <svg
      ref={svg}
      className={`cst-graph cst-graph-${variant}`}
      viewBox={`0 0 ${W} ${height}`}
      role={interactive ? "group" : undefined}
      aria-label={interactive ? "Your week, one node per day" : undefined}
      aria-hidden={interactive ? undefined : true}
      focusable="false"
      onPointerMove={(event) => {
        if (!drag.current) return;
        const p = toSvg(event);
        const n = byId.get(drag.current);
        if (p && n) {
          n.x = p.x;
          n.y = p.y;
          setFrame((f) => f + 1);
        }
      }}
      onPointerUp={() => {
        if (!drag.current) return;
        const n = byId.get(drag.current);
        if (n) n.pinned = false;
        drag.current = null;
        alpha.current = Math.max(alpha.current, 0.4);
        if (!reducedMotion()) {
          const tick = () => {
            step(g.nodes, g.edges, height, alpha.current);
            alpha.current *= 0.985;
            setFrame((f) => f + 1);
            if (alpha.current > 0.02 && !drag.current) requestAnimationFrame(tick);
          };
          requestAnimationFrame(tick);
        }
      }}
    >
      {avatar && (
        <defs>
          <clipPath id={clipId}>
            <circle cx={0} cy={0} r={byId.get("you")!.r} />
          </clipPath>
        </defs>
      )}
      <g className="cst-edges">
        {g.edges.map((e) => {
          const a = byId.get(e.a)!;
          const b = byId.get(e.b)!;
          const lit = hover !== null && neighbors.has(e.a) && neighbors.has(e.b) && (e.a === hover || e.b === hover);
          return (
            <line
              key={`${e.a}-${e.b}`}
              x1={a.x}
              y1={a.y}
              x2={b.x}
              y2={b.y}
              className={`cst-edge is-${e.kind}${lit ? " is-lit" : ""}${hover && !lit ? " is-dim" : ""}`}
            />
          );
        })}
      </g>
      {g.nodes.map((n) => {
        const focusable = interactive && n.kind === "day";
        const name = n.kind === "day" ? `${DAY_NAMES[(n.day ?? 1) - 1]}: ${n.sub}` : n.kind === "you" ? "You" : `Sunday: ${n.sub}`;
        return (
          <g
            key={n.id}
            className={`cst-node is-${n.kind}${n.state ? ` is-${n.state}` : ""}${dim(n.id) ? " is-dim" : ""}${hover === n.id ? " is-hover" : ""}`}
            transform={`translate(${n.x} ${n.y})`}
            tabIndex={focusable ? 0 : undefined}
            role={focusable ? "button" : undefined}
            aria-label={focusable ? `${name}. Open this question.` : undefined}
            onPointerEnter={interactive ? () => setHover(n.id) : undefined}
            onPointerLeave={interactive ? () => setHover((h) => (h === n.id ? null : h)) : undefined}
            onFocus={focusable ? () => setHover(n.id) : undefined}
            onBlur={focusable ? () => setHover(null) : undefined}
            onPointerDown={
              interactive
                ? (event) => {
                    (event.currentTarget.ownerSVGElement ?? svg.current)?.setPointerCapture?.(event.pointerId);
                    drag.current = n.id;
                    n.pinned = true;
                  }
                : undefined
            }
            onClick={focusable && n.day ? () => onSelectDay?.(n.day!) : undefined}
            onKeyDown={
              focusable && n.day
                ? (event) => {
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault();
                      onSelectDay?.(n.day!);
                    }
                  }
                : undefined
            }
          >
            {n.state === "answered" && <circle r={n.r + 7} className="cst-node-halo" />}
            {n.state === "today" && <circle r={n.r + 6} className="cst-node-pulse" />}
            <circle r={n.r} className="cst-node-core" />
            {n.kind === "you" && avatar && (
              <image
                href={avatar}
                x={-n.r}
                y={-n.r}
                width={n.r * 2}
                height={n.r * 2}
                clipPath={`url(#${clipId})`}
                preserveAspectRatio="xMidYMid slice"
              />
            )}
            {!compact && (
              <text className="cst-node-label" y={n.r + 15} textAnchor="middle">
                {n.label}
              </text>
            )}
            {!compact && n.kind !== "you" && (
              <text className="cst-node-sub" y={n.r + 28} textAnchor="middle">
                {n.sub}
              </text>
            )}
          </g>
        );
      })}
    </svg>
  );
}

function previousAlpha(g: { nodes: GNode[] } | null): number {
  return g ? 0.6 : 0;
}
