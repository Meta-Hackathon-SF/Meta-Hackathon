/*
 * Starfield renderer for the Space tab (ported from the SpaceV4Phone design).
 *
 * Pure drawing: positions come from a seeded PRNG, never from player data. The
 * stars around "me" are illustrative only; the UI labels them as a preview
 * until contract 3.0.0 delivers real DailyConstellationsView anchors.
 */

export type SkyMode = "home" | "daily" | "sky" | "forming" | "main";

export const SKY_COLORS = ["#4599FF", "#2CC7C0", "#5BD27A", "#F5B841", "#F07196"] as const;
const RGB = ["69,153,255", "44,199,192", "91,210,122", "245,184,65", "240,113,150"];
/** Member star sprite indices (into the sprite table). */
const MEMBER_SPRITES = [9, 7, 10, 8];

export interface SkyInput {
  mode: SkyMode;
  /** Days (1-5) the player answered. */
  answered: ReadonlySet<number>;
  viewDay: number;
  emptyDay: boolean;
  noMatch: boolean;
  /** Freeze at the end state (reduced motion). */
  still: boolean;
  /** Week sky: highlight one day's lines (1-5); others dim. */
  focusDay?: number | null;
}

export interface SkyHooks {
  onCount?: (value: number) => void;
  onProgress?: (value: number) => void;
  onSettled?: () => void;
}

type Twinkle = { amp: number; f1: number; f2: number; f3: number; p1: number; p2: number; p3: number; fp: number; d: number; a: number };
type Pt = { x: number; y: number; id: string; k?: number; sz?: number } & Partial<Twinkle>;
type Edge = [number, number, number];
type Con = { pts: Pt[]; edges: Edge[] };

const cl = (v: number) => Math.max(0, Math.min(1, v));
const ease = (p: number) => {
  p = cl(p);
  return p < 0.5 ? 4 * p * p * p : 1 - Math.pow(-2 * p + 2, 3) / 2;
};
const easeOut = (p: number) => 1 - Math.pow(1 - cl(p), 3);

let spriteCache: HTMLCanvasElement[] | null = null;
function sprites(): HTMLCanvasElement[] {
  if (spriteCache) return spriteCache;
  spriteCache = ["155,176,255", "202,215,255", "255,255,255", "255,241,224", "255,210,161", "220,232,255", ...RGB].map((rgb) => {
    const c = document.createElement("canvas");
    c.width = c.height = 64;
    const g = c.getContext("2d")!;
    const gr = g.createRadialGradient(32, 32, 0, 32, 32, 32);
    gr.addColorStop(0, "rgba(255,255,255,.9)");
    gr.addColorStop(0.07, "rgba(255,255,255,.55)");
    gr.addColorStop(0.16, `rgba(${rgb},.26)`);
    gr.addColorStop(0.34, `rgba(${rgb},.07)`);
    gr.addColorStop(0.62, `rgba(${rgb},.015)`);
    gr.addColorStop(1, `rgba(${rgb},0)`);
    g.fillStyle = gr;
    g.fillRect(0, 0, 64, 64);
    return c;
  });
  return spriteCache;
}

const FILL = ["rgb(155,176,255)", "rgb(202,215,255)", "rgb(255,255,255)", "rgb(255,241,224)", "rgb(255,210,161)"];

export class SkyRenderer {
  private key = "";
  private W = 0;
  private H = 0;
  private bg!: HTMLCanvasElement;
  private tw: (Twinkle & { x: number; y: number; s: number; col: number })[] = [];
  private cx = 0;
  private cy = 0;
  private me!: Pt;
  private close: Pt[] = [];
  private days: Record<number, Con[]> = {};
  private second: { d: number; pts: Pt[]; bend: number }[] = [];
  private emap: Record<string, { a: Pt; b: Pt; bend: number; days: number[] }> = {};
  private amb: { pts: { x: number; y: number }[]; edges: Edge[]; per: number; ph: number }[] = [];
  private nb: { x: number; y: number; a: number; col: number; sz: number; f1: number; f2: number; p1: number; p2: number }[] = [];
  private anchors: { x: number; y: number }[] = [];
  private meAnchor = { x: 0, y: 0 };
  private loop: { x: number; y: number }[] = [];
  private attempts: { from: Pt; to: Pt; kept: boolean; tree: boolean }[] = [];
  private spr: HTMLCanvasElement[] = [];

  build(W: number, H: number) {
    const dpr = window.devicePixelRatio || 1;
    const key = `${W}x${H}@${dpr}`;
    if (this.key === key) return;
    this.key = key;
    this.W = W;
    this.H = H;
    let seed = 46;
    const r = () => {
      seed |= 0;
      seed = (seed + 0x6d2b79f5) | 0;
      let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
    this.spr = sprites();
    const pick = () => {
      const v = r();
      return v < 0.12 ? 0 : v < 0.35 ? 1 : v < 0.75 ? 2 : v < 0.93 ? 3 : 4;
    };
    const tw = (lo: number, hi: number): Twinkle => ({
      amp: lo + (hi - lo) * r(), f1: 2 + 5 * r(), f2: 7 + 10 * r(), f3: 0.25 + 0.6 * r(),
      p1: r() * 6.283, p2: r() * 6.283, p3: r() * 6.283, fp: r() * 6.283, d: r() * 1200, a: 1,
    });
    const gauss = () => (r() + r() + r() + r() - 2) * 0.9;

    const bc = document.createElement("canvas");
    bc.width = Math.round(W * dpr);
    bc.height = Math.round(H * dpr);
    const g = bc.getContext("2d")!;
    g.scale(dpr, dpr);
    ([[0.18, 0.32, 280, "60,90,200", 0.06], [0.78, 0.6, 320, "120,70,190", 0.05], [0.45, 0.9, 240, "40,130,190", 0.04]] as const).forEach(([fx, fy, rad, c, a]) => {
      const gr = g.createRadialGradient(fx * W, fy * H, 0, fx * W, fy * H, rad);
      gr.addColorStop(0, `rgba(${c},${a})`);
      gr.addColorStop(1, `rgba(${c},0)`);
      g.fillStyle = gr;
      g.fillRect(0, 0, W, H);
    });
    const tints = ["190,205,255", "230,238,255", "255,244,228", "255,226,190"];
    const dust = Math.round(4200 * Math.min(2.5, (W * H) / (390 * 844)));
    for (let i = 0; i < dust; i++) {
      const t = r(), x = t * W * 1.3 - W * 0.15, y = H * (0.8 - 0.62 * t) + gauss() * H * 0.11;
      if (x < 0 || x > W || y < 0 || y > H) continue;
      g.fillStyle = `rgba(${tints[Math.floor(r() * 4)]},${0.04 + 0.2 * r()})`;
      const sz = 0.4 + 0.6 * r();
      g.fillRect(x, y, sz, sz);
    }
    for (let i = 0; i < dust * 0.62; i++) {
      const x = r() * W, y = r() * H, m = Math.pow(r(), 5);
      g.fillStyle = `rgba(${tints[Math.floor(r() * 4)]},${0.1 + 0.4 * m + 0.1 * r()})`;
      g.beginPath();
      g.arc(x, y, 0.35 + m * 0.75, 0, 6.283);
      g.fill();
    }
    this.bg = bc;
    this.tw = [];
    for (let i = 0; i < 700; i++) {
      const m = Math.pow(r(), 4);
      this.tw.push({ x: r() * W, y: r() * H, s: 0.7 + m * 2.2, col: pick(), ...tw(0.45, 0.92), a: 0.25 + 0.5 * r() });
    }
    const cx = W / 2, cy = H * 0.45;
    this.cx = cx;
    this.cy = cy;
    const sc = Math.min(1.25, Math.max(0.8, Math.min(W / 390, H / 700)));
    this.me = { x: cx, y: cy, id: "me" };
    this.close = ([[-74, -104], [92, -66], [70, 96], [-100, 60]] as const).map(([dx, dy], k) => ({ x: cx + dx * sc, y: cy + dy * sc, id: "c" + k, k, ...tw(0.2, 0.45), a: 1 }));
    const ok = (x: number, y: number) => x > 14 && x < W - 14 && y > 96 && y < H - 130;
    const shuffle = <T,>(a: T[]) => {
      for (let i = a.length - 1; i > 0; i--) {
        const j = Math.floor(r() * (i + 1));
        [a[i], a[j]] = [a[j], a[i]];
      }
      return a;
    };
    const DIRS = [-2.3, -0.5, 0.95, 2.35, 3.9], NG = [2, 1, 3, 1, 2];
    let xid = 0;
    this.days = {};
    this.second = [];
    this.emap = {};
    for (let d = 1; d <= 5; d++) {
      this.days[d] = [];
      const pool = shuffle([0, 1, 2, 3]);
      for (let gi = 0; gi < NG[d - 1]; gi++) {
        const pts: Pt[] = [this.me], edges: Edge[] = [];
        const ks = pool.splice(0, Math.min(pool.length, 1 + Math.floor(r() * 2))), chain = r() < 0.5;
        let prev = 0;
        ks.forEach((k) => {
          pts.push(this.close[k]);
          edges.push([chain ? prev : 0, pts.length - 1, (r() < 0.5 ? -1 : 1) * (0.02 + r() * 0.04)]);
          prev = pts.length - 1;
        });
        const nt = 1 + Math.floor(r() * 3);
        for (let t = 0; t < nt; t++) {
          const si = Math.floor(r() * pts.length), s0 = pts[si];
          let hd = si === 0 ? DIRS[d - 1] + gi * 2.1 + t * 1.7 + (r() - 0.5) * 1.4 : Math.atan2(s0.y - cy, s0.x - cx) + (r() - 0.5) * 1.2;
          const budget = (90 + r() * 260) * sc;
          let dist = 0, last = si, px = s0.x, py = s0.y, curv = (r() < 0.5 ? -1 : 1) * (0.12 + r() * 0.25);
          for (let q = 0; q < 8 && dist < budget; q++) {
            let placed = false;
            for (let tr = 0; tr < 8 && !placed; tr++) {
              const st = (34 + r() * 46) * sc, h2 = hd + (tr > 3 ? (r() - 0.5) * 2 : 0) + (r() - 0.5) * 0.3;
              const x = px + Math.cos(h2) * st, y = py + Math.sin(h2) * st * 1.2;
              if (!ok(x, y) || pts.some((p) => Math.hypot(p.x - x, p.y - y) < 30)) continue;
              pts.push({ x, y, id: "x" + xid++, sz: 10 + r() * 7, ...tw(0.2, 0.45), a: 0.55 + 0.4 * r() });
              edges.push([last, pts.length - 1, (r() - 0.5) * 0.12]);
              last = pts.length - 1;
              px = x;
              py = y;
              dist += st;
              hd = h2 + curv;
              if (r() < 0.3) curv = -curv;
              placed = true;
            }
            if (!placed) break;
          }
        }
        this.days[d].push({ pts, edges });
        edges.forEach(([i, j, b]) => {
          const a = pts[i], c2 = pts[j], k = a.id < c2.id ? a.id + "|" + c2.id : c2.id + "|" + a.id;
          (this.emap[k] = this.emap[k] || { a, b: c2, bend: b, days: [] }).days.push(d);
        });
        if (r() < 0.45) {
          const xs = pts.filter((p) => p.id[0] === "x");
          if (xs.length) {
            const p0 = xs[Math.floor(r() * xs.length)], sp: Pt[] = [p0];
            let lx = p0.x, ly = p0.y, h = r() * 6.283;
            for (let q = 0; q < 3; q++) {
              h += (r() - 0.3) * 0.9;
              lx += Math.cos(h) * (22 + r() * 24);
              ly += Math.sin(h) * (22 + r() * 24);
              sp.push({ x: lx, y: ly, id: "s", ...tw(0.2, 0.5), a: 0.4 });
            }
            this.second.push({ d, pts: sp, bend: (r() - 0.5) * 0.25 });
          }
        }
      }
    }
    this.amb = [];
    for (let i = 0; i < 9; i++) {
      const n = 4 + Math.floor(r() * 4);
      let x = 20 + r() * (W - 40), y = 90 + r() * (H - 200), h = r() * 6.283;
      const pts = [{ x, y }], edges: Edge[] = [];
      for (let q = 1; q < n; q++) {
        h += (r() - 0.5) * 1.4;
        x += Math.cos(h) * (28 + r() * 40);
        y += Math.sin(h) * (28 + r() * 40);
        if (x < 8 || x > W - 8 || y < 80 || y > H - 100) break;
        pts.push({ x, y });
        edges.push([q - 1, q, (r() - 0.5) * 0.12]);
      }
      if (pts.length > 2) this.amb.push({ pts, edges, per: 11 + r() * 10, ph: r() * 30 });
    }
    this.nb = [];
    for (let i = 0, guard = 0; i < 38 && guard < 2000; i++, guard++) {
      const an = r() * 6.283, dd = 60 + r() * Math.min(W, H) * 0.5, x = cx + Math.cos(an) * dd, y = cy + Math.sin(an) * dd * 1.25;
      if (x < 10 || x > W - 10 || y < 100 || y > H - 190) {
        i--;
        continue;
      }
      this.nb.push({ x, y, a: 0.25 + 0.35 * r(), col: pick(), sz: 1.2 + 1.8 * r(), f1: 2.5 + 6 * r(), f2: 4 + 9 * r(), p1: r() * 6.283, p2: r() * 6.283 });
    }
    const L = Math.min(W * 0.4, 260);
    const lem = (t: number) => {
      const s = Math.sin(t), c = Math.cos(t), q = 1 + s * s;
      return { x: cx + (L * c) / q, y: cy + ((L * s * c) / q) * 1.35 };
    };
    this.anchors = [2.5, 5.9, 0.35, 3.6].map(lem);
    this.meAnchor = lem(Math.PI / 2);
    // Meta logo: one smooth infinity ribbon through the member anchors, starting and ending at "me".
    this.loop = [];
    for (let i = 0; i <= 260; i++) {
      const p = lem(Math.PI / 2 + (i / 260) * Math.PI * 2);
      this.loop.push(p);
    }
    const cand = Object.values(this.days).flat().flatMap((c) => c.pts.filter((p) => p.id[0] === "x"));
    const dst = (a: Pt, b: Pt) => Math.hypot(a.x - b.x, a.y - b.y);
    // Depth-first search with backtracking, not breadth-first: follow one path as deep as it goes,
    // probe the nearest candidates at each step, and when a branch dead-ends walk back and try another.
    // Failed probes flash red and retract; the path that reaches a real match stays lit.
    const pool = [...this.close, ...cand.sort((a, b) => dst(a, this.me) - dst(b, this.me)).slice(0, 26)];
    const at: typeof this.attempts = [];
    const seen = new Set<Pt>([this.me]);
    const stack: Pt[] = [this.me];
    let left = this.close.length;
    let picks = 0;
    for (let guard = 0; left > 0 && guard < 500; guard++) {
      const top = stack[stack.length - 1];
      const options = pool.filter((p) => !seen.has(p)).sort((a, b) => dst(a, top) - dst(b, top)).slice(0, 3);
      let advanced = false;
      for (const o of options) {
        seen.add(o);
        if (o.id[0] === "c") {
          at.push({ from: top, to: o, kept: true, tree: true });
          stack.push(o);
          left--;
          advanced = true;
          break;
        }
        // Every third decoy looks promising: walk into it (depth), then dead-end and backtrack later.
        if (stack.length < 5 && ++picks % 3 === 0) {
          at.push({ from: top, to: o, kept: false, tree: true });
          stack.push(o);
          advanced = true;
          break;
        }
        at.push({ from: top, to: o, kept: false, tree: false }); // probe failed
      }
      if (advanced) continue;
      if (stack.length <= 1) break;
      const dead = stack.pop() as Pt; // dead end: retract to the parent and try a sibling branch
      at.push({ from: dead, to: stack[stack.length - 1], kept: false, tree: false });
    }
    this.attempts = at;
  }

  private lvl(s: Partial<Twinkle>, el: number, ts: number, startup: boolean) {
    const f1 = s.f1 ?? 3, f2 = s.f2 ?? 8, f3 = s.f3 ?? 0.5;
    const n = 0.5 * Math.sin(ts * f1 + (s.p1 ?? 0)) + 0.3 * Math.sin(ts * f2 + (s.p2 ?? 0)) + 0.2 * Math.sin(ts * f3 + (s.p3 ?? 0));
    const base = (s.a ?? 1) * (1 - (s.amp ?? 0.3) * (0.5 + 0.5 * n));
    if (!startup) return base;
    const u = el - 150 - (s.d ?? 0), dim = 0.04;
    if (u < 0) return dim;
    if (u < 600) {
      const k = u / 600, on = Math.sin(u * 0.05 + (s.fp ?? 0) * 5) * Math.sin(u * 0.017 + (s.fp ?? 0)) > -0.15 ? 1 : 0.12;
      return dim + (base - dim) * on * (0.3 + 0.7 * k);
    }
    return base;
  }

  private spot(ctx: CanvasRenderingContext2D, col: number, x: number, y: number, R: number, a: number, noCore = false) {
    if (a <= 0.003) return;
    a = Math.min(1, a);
    ctx.globalAlpha = a;
    ctx.drawImage(this.spr[col], x - R, y - R, R * 2, R * 2);
    if (noCore) return;
    ctx.fillStyle = "#fff";
    ctx.globalAlpha = Math.min(1, a * 1.1);
    ctx.beginPath();
    ctx.arc(x, y, Math.max(0.7, R * 0.1), 0, 6.283);
    ctx.fill();
  }

  private seg(ctx: CanvasRenderingContext2D, a: { x: number; y: number }, b: { x: number; y: number }, ra: number, rb: number, p: number, alpha: number) {
    const dx = b.x - a.x, dy = b.y - a.y, L = Math.hypot(dx, dy);
    if (L < ra + rb + 2 || p <= 0 || alpha <= 0) return;
    const t0 = ra / L, t1 = t0 + (1 - rb / L - t0) * p;
    ctx.globalAlpha = alpha;
    ctx.beginPath();
    ctx.moveTo(a.x + dx * t0, a.y + dy * t0);
    ctx.lineTo(a.x + dx * t1, a.y + dy * t1);
    ctx.stroke();
  }

  private drawBg(ctx: CanvasRenderingContext2D, el: number, ts: number, startup: boolean, dim: number) {
    const su = startup ? cl((el - 100) / 900) : 1;
    ctx.globalAlpha = dim * su;
    ctx.drawImage(this.bg, 0, 0, this.W, this.H);
    for (const s of this.tw) {
      const a = this.lvl(s, el, ts, startup) * dim;
      if (a < 0.01) continue;
      ctx.globalAlpha = Math.min(1, a);
      ctx.fillStyle = FILL[s.col];
      ctx.beginPath();
      ctx.arc(s.x, s.y, s.s * (0.35 + 0.35 * Math.min(1, a / 0.5)), 0, 6.283);
      ctx.fill();
      if (s.s > 1.1) this.spot(ctx, s.col, s.x, s.y, s.s * 3, a * 0.6, true);
    }
  }

  private drawAmbient(ctx: CanvasRenderingContext2D, ts: number, dim: number) {
    ctx.lineWidth = 0.7;
    for (const c of this.amb) {
      const u = ((ts + c.ph) % c.per) / c.per;
      const env = u < 0.3 ? ease(u / 0.3) : u < 0.7 ? 1 : 1 - ease((u - 0.7) / 0.3), n = c.edges.length;
      ctx.strokeStyle = "rgb(200,214,255)";
      c.edges.forEach(([i, j], k) => this.seg(ctx, c.pts[i], c.pts[j], 2, 2, cl(cl(u / 0.3) * n - k), 0.24 * env * dim));
      c.pts.forEach((p) => this.spot(ctx, 1, p.x, p.y, 5, (0.16 + 0.3 * env) * dim, true));
    }
  }

  private drawNb(ctx: CanvasRenderingContext2D, ts: number, dim: number) {
    for (const s of this.nb) {
      const n = 0.5 + 0.5 * Math.sin(ts * s.f1 + s.p1) * Math.sin(ts * s.f2 + s.p2);
      this.spot(ctx, s.col, s.x, s.y, s.sz * 3.4, s.a * (0.04 + 0.96 * n * n * n) * dim);
    }
  }

  private drawCon(ctx: CanvasRenderingContext2D, con: Con, d: number, p: number, alpha: number, ts: number, starA?: number) {
    ctx.strokeStyle = `rgb(${RGB[d - 1]})`;
    ctx.lineWidth = 1.1;
    const n = con.edges.length;
    con.edges.forEach(([i, j], k) => this.seg(ctx, con.pts[i], con.pts[j], i === 0 ? 11 : 7, j === 0 ? 11 : 7, cl(p * n - k), alpha * 0.6));
    con.pts.forEach((pt, i) => {
      if (i === 0) return;
      this.spot(ctx, 5 + d, pt.x, pt.y, pt.id[0] === "c" ? 13 : pt.sz || 9, (starA ?? alpha) * this.lvl(pt, 0, ts, false));
    });
  }

  /** The Meta infinity mark, drawn as a lit ribbon along the member anchors. `p` 0..1 traces it on. */
  private drawMetaLogo(ctx: CanvasRenderingContext2D, p: number, ts: number) {
    const n = Math.max(2, Math.floor(this.loop.length * p));
    const pts = this.loop.slice(0, n);
    const xs = this.loop.map((q) => q.x);
    const g = ctx.createLinearGradient(Math.min(...xs), 0, Math.max(...xs), 0);
    g.addColorStop(0, "#0064E0");
    g.addColorStop(0.5, "#0082FB");
    g.addColorStop(1, "#0064E0");
    const trace = () => {
      ctx.beginPath();
      pts.forEach((q, i) => (i ? ctx.lineTo(q.x, q.y) : ctx.moveTo(q.x, q.y)));
    };
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
    const breathe = 0.9 + 0.1 * Math.sin(ts * 1.6);
    ctx.globalAlpha = 0.22 * breathe;
    ctx.strokeStyle = "#1877F2";
    ctx.lineWidth = 34;
    trace();
    ctx.stroke();
    ctx.globalAlpha = 0.95;
    ctx.strokeStyle = g;
    ctx.lineWidth = 15;
    trace();
    ctx.stroke();
    ctx.globalAlpha = 0.55;
    ctx.strokeStyle = "rgba(255,255,255,.85)";
    ctx.lineWidth = 1.6;
    trace();
    ctx.stroke();
    ctx.globalAlpha = 1;
  }

  private drawMe(ctx: CanvasRenderingContext2D, x: number, y: number, a: number, ts: number, big = false) {
    const yt = 0.95 + 0.05 * Math.sin(ts * 3.1) * Math.sin(ts * 1.3), r = big ? 7.5 : 6.5;
    this.spot(ctx, 5, x, y, r * 9, 0.35 * a, true);
    this.spot(ctx, 2, x, y, r * 5.5, a * yt);
    ctx.globalAlpha = a;
    ctx.fillStyle = "#fff";
    ctx.beginPath();
    ctx.arc(x, y, r * 0.55, 0, 6.283);
    ctx.fill();
  }

  /** Draws one frame. `el` is ms since the mode started. Returns true once the intro has settled. */
  frame(ctx: CanvasRenderingContext2D, input: SkyInput, el: number, ts: number, hooks: SkyHooks): boolean {
    const { W, H } = this;
    ctx.globalAlpha = 1;
    ctx.fillStyle = "#03081A";
    ctx.fillRect(-W, -H, W * 3, H * 3);
    if (input.still) el = 1e6;
    const ans = input.answered;
    let settled = false;
    switch (input.mode) {
      case "daily": {
        const vd = input.viewDay, cons = input.emptyDay ? [] : this.days[vd] ?? [];
        this.drawBg(ctx, el, ts, true, 1);
        this.drawNb(ctx, ts, 1);
        this.drawAmbient(ctx, ts, 1);
        for (let d = 1; d < vd; d++) if (ans.has(d)) this.days[d].forEach((cn) => this.drawCon(ctx, cn, d, 1, 0.3, ts, 0.35));
        cons.forEach((cn, ci) => {
          const t = 1500 + ci * 700;
          this.drawCon(ctx, cn, vd, ease((el - t) / 900), 1, ts, cl((el - t - 150) / 500));
        });
        this.drawMe(ctx, this.cx, this.cy, easeOut((el - 300) / 700), ts);
        hooks.onCount?.(easeOut((el - 300) / 1800));
        settled = el > 1500 + cons.length * 700 + 800;
        break;
      }
      case "sky": {
        const fd = input.focusDay ?? null;
        const dimFor = (d: number) => (fd === null || fd === d ? 1 : 0.18);
        this.drawBg(ctx, el, ts, true, 1);
        this.drawNb(ctx, ts, 1);
        this.drawAmbient(ctx, ts, 1);
        const k = cl((el - 1200) / 900);
        hooks.onCount?.(easeOut((el - 300) / 1800));
        ctx.strokeStyle = "#fff";
        ctx.lineWidth = 0.8;
        for (const sd of this.second)
          if (ans.has(sd.d)) {
            const dm = dimFor(sd.d);
            for (let i = 0; i < sd.pts.length - 1; i++) this.seg(ctx, sd.pts[i], sd.pts[i + 1], 6, 4, 1, 0.12 * k * dm);
            sd.pts.slice(1).forEach((p) => this.spot(ctx, 2, p.x, p.y, 5, (p.a ?? 0.4) * k * dm * this.lvl(p, 0, ts, false)));
          }
        for (const e of Object.values(this.emap)) {
          const ds = e.days.filter((d) => ans.has(d));
          if (!ds.length) continue;
          if (fd !== null) {
            const on = ds.includes(fd);
            ctx.strokeStyle = on ? `rgb(${RGB[fd - 1]})` : "#fff";
            ctx.lineWidth = on ? 1.8 : 0.8;
            this.seg(ctx, e.a, e.b, e.a.id === "me" ? 11 : 8, e.b.id === "me" ? 11 : 8, 1, (on ? 0.95 : 0.08) * k);
            continue;
          }
          const multi = ds.length > 1;
          ctx.strokeStyle = multi ? "#fff" : `rgb(${RGB[ds[0] - 1]})`;
          ctx.lineWidth = multi ? 1.4 : 1.1;
          this.seg(ctx, e.a, e.b, e.a.id === "me" ? 11 : 8, e.b.id === "me" ? 11 : 8, 1, (multi ? 0.45 + 0.1 * ds.length : 0.5) * k);
        }
        for (let d = 1; d <= 5; d++)
          if (ans.has(d)) this.days[d].forEach((cn) => cn.pts.forEach((p) => p.id[0] === "x" && this.spot(ctx, 5 + d, p.x, p.y, fd === d ? 20 : 17, k * dimFor(d) * this.lvl(p, 0, ts, false))));
        this.close.forEach((p) => {
          let n = 0;
          for (let d = 1; d <= 5; d++) if (ans.has(d) && this.days[d].some((cn) => cn.pts.includes(p))) n++;
          if (n) this.spot(ctx, 2, p.x, p.y, 8 + 4 * n, k * (0.5 + 0.12 * n) * this.lvl(p, 0, ts, false));
        });
        this.drawMe(ctx, this.cx, this.cy, easeOut((el - 300) / 700), ts);
        settled = el > 2400;
        break;
      }
      case "forming": {
        const fp = cl(el / 8000);
        this.drawBg(ctx, 1e6, ts, false, 0.8);
        this.drawAmbient(ctx, ts, 0.8);
        for (let d = 1; d <= 5; d++) if (ans.has(d)) this.days[d].forEach((cn) => this.drawCon(ctx, cn, d, 1, 0.16, ts, 0.3));
        const N = this.attempts.length, w = 3 / N, keptN = [0, 0, 0, 0];
        this.attempts.forEach((a, i) => {
          const u = (fp - (i / N) * (1 - w)) / w;
          if (u <= 0) return;
          const grow = cl(u / 0.35);
          let alpha = 0.75;
          if (u > 0.6) {
            const c = cl((u - 0.6) / 0.4);
            alpha = a.kept ? 0.75 - 0.2 * c : a.tree ? 0.75 - 0.45 * c : 0.75 * (1 - c);
          }
          if (a.kept && u > 0.6 && a.to.k !== undefined) keptN[a.to.k]++;
          ctx.strokeStyle = a.kept && u > 0.6 ? "rgb(205,218,250)" : !a.kept && !a.tree && u > 0.35 ? "rgb(255,140,160)" : "#fff";
          ctx.lineWidth = 1.2;
          this.seg(ctx, a.from, a.to, a.from.id === "me" ? 11 : 8, 8, grow, alpha);
          if (u < 1 && !a.kept) this.spot(ctx, a.tree ? 2 : 3, a.to.x, a.to.y, a.tree ? 9 : 12, 0.6 * (1 - cl((u - 0.6) / 0.4)));
        });
        this.close.forEach((p, k) => this.spot(ctx, 2, p.x, p.y, 10 + 6 * Math.min(1, keptN[k]), (0.45 + 0.5 * Math.min(1, keptN[k])) * this.lvl(p, 0, ts, false)));
        this.drawMe(ctx, this.cx, this.cy, 1, ts);
        hooks.onProgress?.(fp);
        settled = fp >= 1;
        break;
      }
      case "main": {
        const fade = ease(el / 1200);
        this.drawBg(ctx, 1e6, ts, false, 1 - 0.45 * fade);
        this.drawNb(ctx, ts, 1 - 0.45 * fade);
        this.drawAmbient(ctx, ts, 1 - 0.45 * fade);
        for (let d = 1; d <= 5; d++) if (ans.has(d)) this.days[d].forEach((cn) => this.drawCon(ctx, cn, d, 1, 0.4 * (1 - fade), ts, 0.5 * (1 - fade)));
        if (input.noMatch) this.drawMe(ctx, this.cx, this.cy, 1, ts);
        else {
          const mv = ease((el - 700) / 1500), lp = ease((el - 2000) / 1300);
          const pos = this.close.map((p, k) => ({ x: p.x + (this.anchors[k].x - p.x) * mv, y: p.y + (this.anchors[k].y - p.y) * mv }));
          const meP = { x: this.cx + (this.meAnchor.x - this.cx) * mv, y: this.cy + (this.meAnchor.y - this.cy) * mv };
          if (lp > 0) this.drawMetaLogo(ctx, lp, ts);
          if (mv < 1) {
            ctx.strokeStyle = "#fff";
            ctx.lineWidth = 1.2;
            pos.forEach((p) => this.seg(ctx, meP, p, 11, 9, 1, 0.4 * (1 - lp)));
          }
          pos.forEach((p, k) => this.spot(ctx, MEMBER_SPRITES[k], p.x, p.y, 16 + 4 * mv, 0.95 * this.lvl(this.close[k], 0, ts, false) + 0.05));
          this.drawMe(ctx, meP.x, meP.y, 1, ts, true);
        }
        settled = el > 3300;
        break;
      }
      default: {
        this.drawBg(ctx, el, ts, true, 1);
        this.drawAmbient(ctx, ts, 1);
        this.drawNb(ctx, ts, 0.7);
        const gl = ctx.createRadialGradient(W / 2, H + 40, 0, W / 2, H + 40, H * 0.72);
        gl.addColorStop(0, "rgba(24,119,242,.34)");
        gl.addColorStop(0.5, "rgba(24,119,242,.1)");
        gl.addColorStop(1, "rgba(0,0,0,0)");
        ctx.globalAlpha = 1;
        ctx.fillStyle = gl;
        ctx.fillRect(0, 0, W, H);
        settled = true;
      }
    }
    ctx.globalAlpha = 1;
    if (settled) hooks.onSettled?.();
    return settled;
  }
}
