/*
 * Telescoping transition played when a player "goes into the sky": an eyepiece iris
 * opens while stars streak outward from the centre, then the sky settles. Pure
 * presentation; skipped for reduced motion. Never carries any data.
 */
import { useEffect, useRef, useState } from "react";

const DURATION_MS = 1500;
const STREAKS = 90;

const reduced = () =>
  typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

export default function Telescope({ onDone }: { onDone?: () => void }) {
  const canvas = useRef<HTMLCanvasElement | null>(null);
  const [live, setLive] = useState(() => !reduced());

  useEffect(() => {
    if (!live) {
      onDone?.();
      return;
    }
    const el = canvas.current;
    const ctx = el?.getContext("2d");
    if (!el || !ctx) return;
    const dpr = window.devicePixelRatio || 1;
    const W = el.offsetWidth, H = el.offsetHeight;
    el.width = Math.round(W * dpr);
    el.height = Math.round(H * dpr);
    ctx.scale(dpr, dpr);
    const stars = Array.from({ length: STREAKS }, (_, i) => ({
      a: (i / STREAKS) * Math.PI * 2 + ((i * 7919) % 100) / 100,
      r0: 0.04 + ((i * 104729) % 100) / 400,
      v: 0.6 + (((i * 15485863) % 100) / 100) * 0.9,
    }));
    const reach = Math.hypot(W, H) / 2;
    const t0 = performance.now();
    let raf = 0;
    const tick = (now: number) => {
      const k = Math.min(1, (now - t0) / DURATION_MS);
      const e = 1 - Math.pow(1 - k, 3);
      ctx.clearRect(0, 0, W, H);
      ctx.save();
      ctx.translate(W / 2, H / 2);
      ctx.lineCap = "round";
      for (const s of stars) {
        const head = (s.r0 + e * s.v) * reach;
        const tail = Math.max(s.r0 * reach, head - (1 - k) * reach * 0.45 * s.v);
        ctx.globalAlpha = Math.sin(Math.PI * Math.min(1, k * 1.15)) * 0.9;
        ctx.strokeStyle = "rgba(205,220,255,1)";
        ctx.lineWidth = 0.6 + 1.4 * e;
        ctx.beginPath();
        ctx.moveTo(Math.cos(s.a) * tail, Math.sin(s.a) * tail);
        ctx.lineTo(Math.cos(s.a) * head, Math.sin(s.a) * head);
        ctx.stroke();
      }
      ctx.restore();
      if (k < 1) raf = requestAnimationFrame(tick);
      else {
        setLive(false);
        onDone?.();
      }
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- plays once per mount
  }, []);

  if (!live) return null;
  return (
    <div className="spc-telescope" aria-hidden="true" data-testid="spc-telescope">
      <canvas ref={canvas} className="spc-telescope-streaks" />
      <div className="spc-telescope-iris" />
      <div className="spc-telescope-ring" />
    </div>
  );
}
