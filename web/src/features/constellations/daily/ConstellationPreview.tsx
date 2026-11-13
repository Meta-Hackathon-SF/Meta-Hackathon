/*
 * The Constellation tab before Sunday: what a constellation is, drawn as an
 * EXAMPLE. You at the centre; the people whose answers meant the most similar
 * things sit closer and shine brighter. No real player, handle or score is
 * shown here. The real view needs per-member closeness from formation (not in
 * contract 2.0.0 yet) and lives with the reveal screen.
 */
import { useId } from "react";
import { Lock } from "lucide-react";
import Avatar from "../../../components/common/Avatar";
import { currentUser } from "../../../data/demo";

// [x, y, closeness 0..1]. Closer = nearer the centre and brighter.
const STARS: [number, number, number][] = [
  [236, 112, 1],
  [392, 98, 0.72],
  [420, 238, 0.45],
  [138, 246, 0.22],
];
// Faint background stars: everyone else this week, not in your constellation.
const DUST: [number, number][] = [
  [70, 60], [110, 230], [520, 70], [560, 200], [470, 260], [60, 150], [530, 140], [140, 30],
  [450, 30], [300, 270], [40, 250], [580, 260],
];

export default function ConstellationPreview({ revealsAt }: { revealsAt: string | null }) {
  const glow = `cst-glow-${useId().replace(/:/g, "")}`;
  const cx = 300;
  const cy = 150;
  return (
    <section className="card cst-panel" aria-labelledby="cst-constellation-title">
      <header className="cst-panel-head">
        <div>
          <h2 id="cst-constellation-title">Your constellation</h2>
          <p className="muted">
            {revealsAt
              ? `Revealed ${new Date(revealsAt).toLocaleString(undefined, { weekday: "long", hour: "numeric", minute: "2-digit" })}`
              : "Revealed on Sunday"}
          </p>
        </div>
        <span className="cst-label cst-label-warn">Example</span>
      </header>

      <div className="cst-sky">
        <svg viewBox="0 0 600 300" className="cst-sky-svg" role="img" aria-label="Example constellation: you in the centre, four people around you; closer people shine brighter.">
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
          {STARS.map(([x, y, c]) => (
            <line key={`l-${x}`} x1={cx} y1={cy} x2={x} y2={y} className="cst-sky-link" style={{ opacity: 0.12 + c * 0.75, strokeWidth: 0.8 + c * 2.4 }} />
          ))}
          {STARS.map(([x, y, c], i) => (
            <g key={`s-${x}`}>
              <circle cx={x} cy={y} r={8 + c * 34} fill={`url(#${glow})`} style={{ opacity: 0.15 + c * 0.85 }} />
              <circle cx={x} cy={y} r={2.5 + c * 5} className="cst-sky-star" style={{ opacity: 0.4 + c * 0.6 }} />
              <text x={x} y={y + 22 + c * 8} textAnchor="middle" className="cst-sky-label" style={{ opacity: 0.45 + c * 0.55 }}>
                Star {i + 1}
              </text>
            </g>
          ))}
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
            <p className="muted">Muse places you with the 3 to 5 people whose answers meant the most similar things this week.</p>
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
