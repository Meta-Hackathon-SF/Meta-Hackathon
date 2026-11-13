/*
 * The Constellation tab's star picture. You at the centre; the people whose
 * answers meant the most similar things sit closer and shine brighter (D009).
 * With `stars` it draws computed bands (fixture: labeled Synthetic players;
 * live: the room's members). Without them it draws a labeled EXAMPLE.
 * Only bands are drawn, never a raw score, never a name.
 */
import { useId } from "react";
import { Lock } from "lucide-react";
import type { Brightness } from "../../../../../contracts/protocol.ts";
import Avatar from "../../../components/common/Avatar";
import { currentUser } from "../../../data/demo";

export interface StarView {
  handle: string;
  color: string;
  brightness: Brightness;
}

const CLOSENESS: Record<Brightness, number> = { bright: 1, mid: 0.55, faint: 0.2 };
const EXAMPLE: StarView[] = [
  { handle: "Star 1", color: "#fff", brightness: "bright" },
  { handle: "Star 2", color: "#fff", brightness: "mid" },
  { handle: "Star 3", color: "#fff", brightness: "mid" },
  { handle: "Star 4", color: "#fff", brightness: "faint" },
];
// Faint background stars: everyone else this week, not in your constellation.
const DUST: [number, number][] = [
  [70, 60], [110, 230], [520, 70], [560, 200], [470, 260], [60, 150], [530, 140], [140, 30],
  [450, 30], [300, 270], [40, 250], [580, 260],
];
const ANGLES = [-60, 20, 140, 210, 290];

function place(i: number, c: number): [number, number] {
  const r = 70 + (1 - c) * 110; // closer = nearer the centre
  const a = (ANGLES[i % ANGLES.length] * Math.PI) / 180;
  return [300 + r * Math.cos(a) * 1.35, 150 + r * Math.sin(a) * 0.75];
}

export default function ConstellationPreview({
  revealsAt,
  stars,
  label,
}: {
  revealsAt: string | null;
  stars?: StarView[] | null;
  label?: string;
}) {
  const glow = `cst-glow-${useId().replace(/:/g, "")}`;
  const real = Boolean(stars && stars.length);
  const shown = real ? stars! : EXAMPLE;
  const cx = 300;
  const cy = 150;
  return (
    <section className="card cst-panel" aria-labelledby="cst-constellation-title" data-testid="cst-constellation">
      <header className="cst-panel-head">
        <div>
          <h2 id="cst-constellation-title">Your constellation</h2>
          <p className="muted">
            {revealsAt
              ? `Revealed ${new Date(revealsAt).toLocaleString(undefined, { weekday: "long", hour: "numeric", minute: "2-digit" })}`
              : real
                ? "Brightness from this week's answers"
                : "Revealed on Sunday"}
          </p>
        </div>
        <span className="cst-label cst-label-warn">{real ? (label ?? "Synthetic players") : "Example"}</span>
      </header>

      <div className="cst-sky">
        <svg
          viewBox="0 0 600 300"
          className="cst-sky-svg"
          role="img"
          aria-label={
            real
              ? `Your constellation: ${shown.map((s) => `${s.handle} ${s.brightness}`).join(", ")}. Closer people shine brighter.`
              : "Example constellation: you in the centre, four people around you; closer people shine brighter."
          }
        >
          <defs>
            <radialGradient id={glow}>
              <stop offset="0%" stopColor="#fff" stopOpacity="0.9" />
              <stop offset="40%" stopColor="#b9a4ff" stopOpacity="0.45" />
              <stop offset="100%" stopColor="#6a4cff" stopOpacity="0" />
            </radialGradient>
          </defs>
          {DUST.map(([x, y]) => (
            <circle key={`${x}-${y}`} cx={x} cy={y} r={1.6} className="cst-dust" />
          ))}
          {shown.map((s, i) => {
            const c = CLOSENESS[s.brightness];
            const [x, y] = place(i, c);
            return (
              <line key={`l-${s.handle}`} x1={cx} y1={cy} x2={x} y2={y} className="cst-sky-link" style={{ opacity: 0.12 + c * 0.75, strokeWidth: 0.8 + c * 2.4 }} />
            );
          })}
          {shown.map((s, i) => {
            const c = CLOSENESS[s.brightness];
            const [x, y] = place(i, c);
            return (
              <g key={`s-${s.handle}`} data-testid="cst-star" data-brightness={s.brightness}>
                <circle cx={x} cy={y} r={8 + c * 34} fill={`url(#${glow})`} style={{ opacity: 0.15 + c * 0.85 }} />
                <circle cx={x} cy={y} r={2.5 + c * 5} className="cst-sky-star" style={{ opacity: 0.4 + c * 0.6 }} />
                <text x={x} y={y + 22 + c * 8} textAnchor="middle" className="cst-sky-label" style={{ opacity: 0.45 + c * 0.55 }}>
                  {s.handle}
                </text>
              </g>
            );
          })}
          <circle cx={cx} cy={cy} r={44} fill={`url(#${glow})`} />
        </svg>
        <div className="cst-sky-you">
          <Avatar person={currentUser} size={44} />
          <span>You</span>
        </div>
      </div>

      <ul className="cst-sky-points">
        <li>
          <span className="cst-sky-dot is-bright" aria-hidden="true" />
          <div>
            <strong>Brighter and closer means more alike</strong>
            <p className="muted">
              Three levels: bright, mid and faint, by how close each person's answers are to yours. Shared Groups and
              events add a little light if you turn on "use my activity".
            </p>
          </div>
        </li>
        <li>
          <span className="cst-sky-dot" aria-hidden="true" />
          <div>
            <strong>Everyone else is the faint sky</strong>
            <p className="muted">Patterns across all players appear only when 3 or more people share them.</p>
          </div>
        </li>
        <li>
          <span className="cst-icon-circle is-small" aria-hidden="true">
            <Lock size={13} />
          </span>
          <div>
            <strong>Stars, not names</strong>
            <p className="muted">You meet as Star handles in an anonymous chat. Names appear only if you both choose to reveal.</p>
          </div>
        </li>
      </ul>
    </section>
  );
}
