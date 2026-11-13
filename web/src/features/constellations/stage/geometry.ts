/*
 * Deterministic drawings for the stage: a constellation "map" per group and the
 * community sky. Positions come from a seeded PRNG, never from player data; the
 * seed is an opaque per-constellation value from the server, so the same group
 * always draws the same shape and different groups draw different shapes.
 */
export type Pt = { x: number; y: number };
export type Map = { stars: Pt[]; edges: [number, number][] };

export function rng(seed: string | number): () => number {
  let s = typeof seed === "number" ? seed | 0 : parseInt(seed.slice(0, 8) || "0", 16) | 0;
  return () => {
    s = (s + 0x6d2b79f5) | 0;
    let t = Math.imul(s ^ (s >>> 15), 1 | s);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** `n` stars spread inside a w x h box (with margin), joined like a star chart:
 * each new star links to its nearest earlier star, plus one closing line. */
export function constellationMap(seed: string, n: number, w: number, h: number, margin = 0.12): Map {
  const r = rng(seed);
  const count = Math.max(1, Math.min(n, 60));
  const stars: Pt[] = [];
  const mx = w * margin, my = h * margin;
  for (let i = 0; i < count; i++) {
    let best: Pt = { x: mx + r() * (w - 2 * mx), y: my + r() * (h - 2 * my) };
    // A few tries to keep stars apart so the shape reads at a glance.
    for (let k = 0; k < 6 && stars.some((p) => Math.hypot(p.x - best.x, p.y - best.y) < Math.min(w, h) / (count > 12 ? 9 : 5)); k++) {
      best = { x: mx + r() * (w - 2 * mx), y: my + r() * (h - 2 * my) };
    }
    stars.push(best);
  }
  const edges: [number, number][] = [];
  for (let i = 1; i < stars.length; i++) {
    let j = 0;
    let d = Infinity;
    for (let k = 0; k < i; k++) {
      const dk = Math.hypot(stars[i].x - stars[k].x, stars[i].y - stars[k].y);
      if (dk < d) {
        d = dk;
        j = k;
      }
    }
    edges.push([j, i]);
  }
  if (stars.length > 3) edges.push([stars.length - 1, Math.floor(r() * (stars.length - 2))]);
  return { stars, edges };
}

/** Scattered positions for `n` loose dots (before Muse has grouped anyone). */
export function scatter(n: number, w: number, h: number, seed = 7): Pt[] {
  const r = rng(seed);
  return Array.from({ length: n }, () => ({ x: 0.04 * w + r() * 0.92 * w, y: 0.08 * h + r() * 0.84 * h }));
}

/** Cell centres for `n` groups laid out over a w x h sky. */
export function cells(n: number, w: number, h: number): { cx: number; cy: number; cw: number; ch: number }[] {
  if (n <= 0) return [];
  const cols = Math.max(1, Math.round(Math.sqrt((n * w) / h)));
  const rows = Math.ceil(n / cols);
  const cw = w / cols, ch = h / rows;
  return Array.from({ length: n }, (_, i) => {
    const row = Math.floor(i / cols);
    const inRow = Math.min(cols, n - row * cols);
    const offset = (w - inRow * cw) / 2;
    return { cx: offset + (i % cols) * cw + cw / 2, cy: row * ch + ch / 2, cw, ch };
  });
}
