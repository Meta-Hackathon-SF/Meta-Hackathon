import { useEffect, useRef } from "react";
import { SkyRenderer, type SkyHooks, type SkyInput } from "./sky";

const reducedMotion = () =>
  typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

/** Animated starfield. Restarts its intro whenever `mode` or `viewDay` changes. */
export default function SkyCanvas({ input, hooks }: { input: Omit<SkyInput, "still">; hooks?: SkyHooks }) {
  const canvas = useRef<HTMLCanvasElement | null>(null);
  const renderer = useRef<SkyRenderer | null>(null);
  const latest = useRef({ input, hooks });
  useEffect(() => {
    latest.current = { input, hooks };
  });

  useEffect(() => {
    const el = canvas.current;
    if (!el) return;
    renderer.current ??= new SkyRenderer();
    const sky = renderer.current;
    const still = reducedMotion();
    const t0 = performance.now();
    let raf = 0;
    let settledOnce = false;
    const tick = (now: number) => {
      const W = el.offsetWidth, H = el.offsetHeight;
      if (!W || !H) {
        raf = requestAnimationFrame(tick);
        return;
      }
      const dpr = window.devicePixelRatio || 1;
      if (el.width !== Math.round(W * dpr) || el.height !== Math.round(H * dpr)) {
        el.width = Math.round(W * dpr);
        el.height = Math.round(H * dpr);
      }
      sky.build(W, H);
      const ctx = el.getContext("2d");
      if (!ctx) return;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      const { input: inp, hooks: h } = latest.current;
      const settled = sky.frame(ctx, { ...inp, still }, now - t0, now / 1000, {
        onCount: h?.onCount,
        onProgress: h?.onProgress,
        onSettled: settledOnce ? undefined : h?.onSettled,
      });
      if (settled) settledOnce = true;
      if (!still || !settled) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [input.mode, input.viewDay, input.emptyDay, input.noMatch]);

  return <canvas ref={canvas} className="spc-canvas" aria-hidden="true" />;
}
