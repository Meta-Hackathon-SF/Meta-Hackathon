/** Circular Facebook Space badge: a feature identity, like Facebook's Memories or Marketplace circles. */
export default function ConstellationsMark({ size = 40 }: { size?: number }) {
  return (
    <span className="cst-mark" style={{ width: size, height: size }} aria-hidden="true">
      <svg viewBox="0 0 40 40" width={size} height={size} focusable="false">
        <g stroke="#fff" strokeWidth="1.6" strokeLinecap="round" opacity="0.85">
          <line x1="11" y1="25" x2="18" y2="14" />
          <line x1="18" y1="14" x2="27" y2="18" />
          <line x1="27" y1="18" x2="30" y2="28" />
          <line x1="11" y1="25" x2="20" y2="29" />
        </g>
        <g fill="#fff">
          <circle cx="11" cy="25" r="2.4" />
          <circle cx="18" cy="14" r="3" />
          <circle cx="27" cy="18" r="2.4" />
          <circle cx="30" cy="28" r="2" />
          <circle cx="20" cy="29" r="2" />
        </g>
      </svg>
    </span>
  );
}
