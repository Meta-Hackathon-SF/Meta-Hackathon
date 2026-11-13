import { useEffect, useRef } from "react";
import { Minus, Plus, RotateCcw } from "lucide-react";
import { SkyRenderer, type SkyHooks, type SkyInput } from "./sky";

const reducedMotion = () =>
  typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

const MIN = 1;
const MAX = 4;

type View = { s: number; x: number; y: number };

/**
 * Animated starfield. Restarts its intro whenever `mode` or `viewDay` changes.
 * `interactive`: drag to pan, wheel / pinch / double-click / buttons to zoom.
 */
export default function SkyCanvas({ input, hooks, interactive = false }: { input: Omit<SkyInput, "still">; hooks?: SkyHooks; interactive?: boolean }) {
  const canvas = useRef<HTMLCanvasElement | null>(null);
  const renderer = useRef<SkyRenderer | null>(null);
  const view = useRef<View>({ s: 1, x: 0, y: 0 });
  const target = useRef<View>({ s: 1, x: 0, y: 0 });
  const latest = useRef({ input, hooks });
  useEffect(() => {
    latest.current = { input, hooks };
  });

  // Clamp so the sky always covers the stage.
  const clamp = (v: View): View => {
    const el = canvas.current;
    const W = el?.offsetWidth ?? 0, H = el?.offsetHeight ?? 0;
    const s = Math.min(MAX, Math.max(MIN, v.s));
    return { s, x: Math.min(0, Math.max(W - W * s, v.x)), y: Math.min(0, Math.max(H - H * s, v.y)) };
  };
  const zoomAt = (factor: number, px: number, py: number, instant = false) => {
    const t = target.current;
    const s = Math.min(MAX, Math.max(MIN, t.s * factor));
    const k = s / t.s;
    target.current = clamp({ s, x: px - (px - t.x) * k, y: py - (py - t.y) * k });
    if (instant) view.current = target.current;
  };
  const center = () => {
    const el = canvas.current;
    return { x: (el?.offsetWidth ?? 0) / 2, y: (el?.offsetHeight ?? 0) / 2 };
  };

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
      // Ease the view toward its target (instant under reduced motion).
      const v = view.current, t = target.current, e = still ? 1 : 0.22;
      view.current = { s: v.s + (t.s - v.s) * e, x: v.x + (t.x - v.x) * e, y: v.y + (t.y - v.y) * e };
      const { s, x, y } = view.current;
      ctx.setTransform(dpr * s, 0, 0, dpr * s, dpr * x, dpr * y);
      const { input: inp, hooks: h } = latest.current;
      const settled = sky.frame(ctx, { ...inp, still }, now - t0, now / 1000, {
        onCount: h?.onCount,
        onProgress: h?.onProgress,
        onSettled: settledOnce ? undefined : h?.onSettled,
      });
      if (settled) settledOnce = true;
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [input.mode, input.viewDay, input.emptyDay, input.noMatch]);

  // Pointer + wheel interaction.
  useEffect(() => {
    const el = canvas.current;
    if (!el || !interactive) return;
    const pts = new Map<number, { x: number; y: number }>();
    let pinch = 0;
    const local = (e: PointerEvent | WheelEvent | MouseEvent) => {
      const r = el.getBoundingClientRect();
      return { x: e.clientX - r.left, y: e.clientY - r.top };
    };
    const down = (e: PointerEvent) => {
      el.setPointerCapture(e.pointerId);
      pts.set(e.pointerId, local(e));
      if (pts.size === 2) {
        const [a, b] = [...pts.values()];
        pinch = Math.hypot(a.x - b.x, a.y - b.y);
      }
    };
    const move = (e: PointerEvent) => {
      const prev = pts.get(e.pointerId);
      if (!prev) return;
      const p = local(e);
      pts.set(e.pointerId, p);
      if (pts.size === 1) {
        const t = target.current;
        target.current = clamp({ s: t.s, x: t.x + p.x - prev.x, y: t.y + p.y - prev.y });
        view.current = target.current;
      } else if (pts.size === 2) {
        const [a, b] = [...pts.values()];
        const d = Math.hypot(a.x - b.x, a.y - b.y);
        if (pinch) zoomAt(d / pinch, (a.x + b.x) / 2, (a.y + b.y) / 2, true);
        pinch = d;
      }
    };
    const up = (e: PointerEvent) => {
      pts.delete(e.pointerId);
      pinch = 0;
    };
    const wheel = (e: WheelEvent) => {
      e.preventDefault();
      const p = local(e);
      zoomAt(Math.exp(-e.deltaY * 0.0022), p.x, p.y);
    };
    const dbl = (e: MouseEvent) => {
      const p = local(e);
      zoomAt(target.current.s >= MAX - 0.01 ? 1 / MAX : 2, p.x, p.y);
    };
    el.addEventListener("pointerdown", down);
    el.addEventListener("pointermove", move);
    el.addEventListener("pointerup", up);
    el.addEventListener("pointercancel", up);
    el.addEventListener("wheel", wheel, { passive: false });
    el.addEventListener("dblclick", dbl);
    return () => {
      el.removeEventListener("pointerdown", down);
      el.removeEventListener("pointermove", move);
      el.removeEventListener("pointerup", up);
      el.removeEventListener("pointercancel", up);
      el.removeEventListener("wheel", wheel);
      el.removeEventListener("dblclick", dbl);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [interactive]);

  return (
    <>
      <canvas ref={canvas} className={`spc-canvas${interactive ? " is-interactive" : ""}`} aria-hidden="true" />
      {interactive && (
        <div className="spc-zoom" role="group" aria-label="Zoom the sky">
          <button type="button" aria-label="Zoom in" onClick={() => zoomAt(1.5, center().x, center().y)}>
            <Plus size={18} />
          </button>
          <button type="button" aria-label="Zoom out" onClick={() => zoomAt(1 / 1.5, center().x, center().y)}>
            <Minus size={18} />
          </button>
          <button type="button" aria-label="Reset view" onClick={() => (target.current = { s: 1, x: 0, y: 0 })}>
            <RotateCcw size={16} />
          </button>
        </div>
      )}
    </>
  );
}
