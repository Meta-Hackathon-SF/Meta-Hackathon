import { useEffect, useState } from "react";

type Phase = "open0" | "aim" | "focus" | "zoom" | "arrive" | "off";

/**
 * Telescope transition played when arriving from the feed card: a lens opens on
 * a small constellation, focuses, then zooms through into Space. Skipped for
 * reduced motion. Purely decorative.
 */
export default function ScopeOverlay({ onDone }: { onDone: () => void }) {
  const reduce = typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
  const [phase, setPhase] = useState<Phase>(reduce ? "off" : "open0");
  useEffect(() => {
    if (reduce) {
      onDone();
      return;
    }
    const steps: [number, Phase][] = [
      [40, "aim"],
      [800, "focus"],
      [1900, "zoom"],
      [2600, "arrive"],
      [3300, "off"],
    ];
    const ids = steps.map(([ms, p]) => window.setTimeout(() => setPhase(p), ms));
    const done = window.setTimeout(onDone, 3300);
    return () => {
      ids.forEach(clearTimeout);
      clearTimeout(done);
    };
  }, [reduce, onDone]);
  if (phase === "off") return null;
  const ring = phase === "aim" || phase === "focus";
  return (
    <div className={`spc-scope is-${phase}`} aria-hidden="true">
      <div className="spc-scope-lens">
        <div className="spc-scope-stars" />
        <div className="spc-scope-glow" />
        <svg viewBox="0 0 300 300" className="spc-scope-svg" fill="none">
          <path d="M70 190 Q70 130 120 110 T190 130 Q232 108 230 70 M190 130 Q222 170 220 210" stroke="rgba(255,255,255,.6)" strokeWidth="1.2" strokeDasharray="500" strokeDashoffset={phase === "open0" || phase === "aim" ? 500 : 0} />
          <g fill="#fff">
            <circle cx="70" cy="190" r="3" />
            <circle cx="120" cy="110" r="4.5" />
            <circle cx="190" cy="130" r="3.5" />
            <circle cx="230" cy="70" r="3" />
            <circle cx="220" cy="210" r="3" />
          </g>
        </svg>
      </div>
      <div className={`spc-scope-ring${ring ? " is-on" : ""}`} />
      <div className={`spc-scope-rim${ring ? " is-on" : ""}`} />
      <div className={`spc-scope-label${ring ? " is-on" : ""}`}>{phase === "focus" ? "THIS WEEK · IN FOCUS" : "FOCUSING…"}</div>
    </div>
  );
}
