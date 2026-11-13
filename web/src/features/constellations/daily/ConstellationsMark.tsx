import { SPACE_LINES, SPACE_STARS } from "../../../components/navigation/spaceMark";

/** Circular Facebook Space badge. Same geometry as the sidebar and tab icons (SPACE_STARS). */
export default function ConstellationsMark({ size = 40 }: { size?: number }) {
  return (
    <span className="cst-mark" style={{ width: size, height: size }} aria-hidden="true">
      <svg viewBox="0 0 36 36" width={size} height={size} focusable="false">
        <g stroke="#fff" strokeWidth="1.5" strokeLinecap="round" opacity="0.85">
          {SPACE_LINES.map(([a, b]) => (
            <line key={`${a}-${b}`} x1={SPACE_STARS[a][0]} y1={SPACE_STARS[a][1]} x2={SPACE_STARS[b][0]} y2={SPACE_STARS[b][1]} />
          ))}
        </g>
        <g fill="#fff">
          {SPACE_STARS.map(([x, y, r]) => (
            <circle key={`${x}-${y}`} cx={x} cy={y} r={r} />
          ))}
        </g>
      </svg>
    </span>
  );
}
