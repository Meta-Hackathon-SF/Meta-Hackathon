/*
 * "Send to Messenger" transition, played when everyone keeps the 24-hour room. The chat panel shrinks
 * into the Messenger logo bubble, folds into a paper plane, flies in an arc to the Messenger icon in
 * the header, and the icon pulses. Presentation only; reduced motion skips it. No data.
 */
import { useEffect, useRef } from "react";

const FLIGHT_MS = 1900;
const reduced = () =>
  typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

function target(): { x: number; y: number } {
  const el = document.querySelector<HTMLElement>('header [aria-label="Messenger"], [aria-label="Messenger"]');
  const r = el?.getBoundingClientRect();
  if (r && r.width) return { x: r.left + r.width / 2, y: r.top + r.height / 2 };
  return { x: window.innerWidth - 56, y: 28 };
}

export default function MessengerSend({ onDone }: { onDone: () => void }) {
  const card = useRef<HTMLDivElement>(null);
  const plane = useRef<SVGSVGElement>(null);

  useEffect(() => {
    const el = card.current;
    if (!el || reduced() || !el.animate) {
      onDone();
      return;
    }
    const t = target();
    const cx = window.innerWidth / 2, cy = window.innerHeight / 2;
    const dx = t.x - cx, dy = t.y - cy;
    const lift = -Math.min(160, window.innerHeight * 0.2); // arc: rise first, then dive to the icon
    const anim = el.animate(
      [
        { transform: "translate(0,0) scale(1) rotate(0deg)", borderRadius: "22px", opacity: 1, offset: 0 },
        { transform: "translate(0,0) scale(0.26) rotate(0deg)", borderRadius: "50%", opacity: 1, offset: 0.28 },
        { transform: "translate(0,0) scale(0.26) rotate(-18deg)", borderRadius: "50%", opacity: 1, offset: 0.4 },
        { transform: `translate(${dx * 0.45}px, ${dy * 0.45 + lift}px) scale(0.2) rotate(-32deg)`, borderRadius: "50%", opacity: 1, offset: 0.68 },
        { transform: `translate(${dx}px, ${dy}px) scale(0.05) rotate(-40deg)`, borderRadius: "50%", opacity: 0.9, offset: 1 },
      ],
      { duration: FLIGHT_MS, easing: "cubic-bezier(0.45, 0, 0.25, 1)", fill: "forwards" },
    );
    // Fold: the panel's contents fade as it becomes a bubble; the plane glyph takes over.
    el.querySelector<HTMLElement>(".spc-msgsend-body")?.animate([{ opacity: 1 }, { opacity: 0 }], { duration: 380, fill: "forwards" });
    plane.current?.animate(
      [
        { opacity: 0, transform: "scale(0.4) rotate(0deg)", offset: 0.15 },
        { opacity: 1, transform: "scale(1) rotate(0deg)", offset: 0.38 },
        { opacity: 1, transform: "scale(1) rotate(8deg)", offset: 1 },
      ],
      { duration: FLIGHT_MS, fill: "forwards" },
    );
    anim.onfinish = () => {
      const icon = document.querySelector<HTMLElement>('[aria-label="Messenger"]');
      icon?.animate(
        [{ transform: "scale(1)" }, { transform: "scale(1.45)" }, { transform: "scale(0.92)" }, { transform: "scale(1)" }],
        { duration: 600, easing: "ease-out" },
      );
      onDone();
    };
    return () => anim.cancel();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- plays once
  }, []);

  return (
    <div className="spc-msgsend" aria-hidden="true" data-testid="spc-send-messenger">
      <div className="spc-msgsend-card" ref={card}>
        <div className="spc-msgsend-body">
          <strong>Your constellation</strong>
          <span>Everyone kept it. Moving to Messenger…</span>
        </div>
        <svg ref={plane} className="spc-msgsend-plane" viewBox="0 0 24 24" width="64" height="64" fill="none">
          <path d="M21 3 3 10.5l6.6 2.4L12 21l2.4-6.6L21 3Z" fill="#fff" />
          <path d="m9.6 12.9 11.4-9.9-8.6 11.6" stroke="#0A7CFF" strokeWidth="1.1" strokeLinejoin="round" />
        </svg>
      </div>
    </div>
  );
}
