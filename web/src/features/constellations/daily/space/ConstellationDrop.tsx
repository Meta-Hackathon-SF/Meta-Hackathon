/*
 * Constellation Drop: a full-screen reveal after a day closes and the player's
 * constellation is ready. Four beats: ready -> formation -> payoff -> signal.
 * Other stars are anonymous; only the player's own star and answer are shown.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Volume2, VolumeX } from "lucide-react";
import { currentUser } from "../../../../data/demo";
import type { CycleClient, CycleDay } from "../client";
import type { DailyConstellation } from "../v3";
import "./drop.css";

type Phase = "ready" | "forming" | "payoff" | "signaled";
/** Slow on purpose: the last star lands near 5s, the last line settles just after. */
const FORM_MS = 6200;
const MIN_OTHERS = 4;
const MAX_OTHERS = 6;
const SHARED_MEANING_MIN = 3;

const dismissKey = (id: string) => `spc-drop:${id}`;
const isDismissed = (id: string) => {
  try {
    return sessionStorage.getItem(dismissKey(id)) === "1";
  } catch {
    return false;
  }
};
const markDismissed = (id: string) => {
  try {
    sessionStorage.setItem(dismissKey(id), "1");
  } catch {
    /* storage unavailable */
  }
};

/** Deterministic 0..1 from a string, so a given constellation always forms the same way. */
function seeded(seed: string) {
  let h = 2166136261;
  for (const ch of seed) h = Math.imul(h ^ ch.charCodeAt(0), 16777619);
  return () => {
    h = Math.imul(h ^ (h >>> 15), 2246822507);
    h = Math.imul(h ^ (h >>> 13), 3266489909);
    return ((h ^= h >>> 16) >>> 0) / 4294967296;
  };
}

interface Star { x: number; y: number; fromX: number; fromY: number; delay: number; r: number }

function layout(id: string, others: number): Star[] {
  const rand = seeded(id);
  return Array.from({ length: others }, (_, i) => {
    const angle = (i / others) * Math.PI * 2 + rand() * 0.7;
    const reach = 20 + rand() * 14;
    const edge = angle + (rand() - 0.5) * 0.5;
    return {
      x: 50 + Math.cos(angle) * reach,
      y: 50 + Math.sin(angle) * reach * 0.78,
      fromX: Math.cos(edge) * 70,
      fromY: Math.sin(edge) * 70,
      delay: 400 + i * 420 + rand() * 160,
      r: 0.7 + rand() * 0.5,
    };
  });
}

/** A slightly bowed line with a faint tremor, so the constellation reads as drawn by hand rather than ruled. */
function sketchPath(a: { x: number; y: number }, b: { x: number; y: number }, bow: number) {
  const dx = b.x - a.x;
  const dy = b.y - a.y;
  const c1x = a.x + dx * 0.33 + dy * bow;
  const c1y = a.y + dy * 0.33 - dx * bow;
  const c2x = a.x + dx * 0.68 + dy * bow * 0.55;
  const c2y = a.y + dy * 0.68 - dx * bow * 0.55;
  const f = (n: number) => n.toFixed(2);
  return `M${f(a.x)} ${f(a.y)} C${f(c1x)} ${f(c1y)} ${f(c2x)} ${f(c2y)} ${f(b.x)} ${f(b.y)}`;
}

function useChime() {
  const [on, setOn] = useState(false);
  const ctx = useRef<AudioContext | null>(null);
  const play = useCallback(
    (freq: number) => {
      if (!on) return;
      try {
        ctx.current ??= new AudioContext();
        const c = ctx.current;
        const osc = c.createOscillator();
        const gain = c.createGain();
        osc.type = "sine";
        osc.frequency.value = freq;
        gain.gain.setValueAtTime(0.0001, c.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.05, c.currentTime + 0.04);
        gain.gain.exponentialRampToValueAtTime(0.0001, c.currentTime + 1.2);
        osc.connect(gain).connect(c.destination);
        osc.start();
        osc.stop(c.currentTime + 1.25);
      } catch {
        /* audio unavailable: stay silent */
      }
    },
    [on],
  );
  useEffect(() => () => void ctx.current?.close().catch(() => undefined), []);
  return { on, setOn, play };
}

function usePrefersReducedMotion() {
  return typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches === true;
}

export interface ConstellationDropProps {
  constellation: DailyConstellation;
  answerText: string;
  onEnter: () => void;
  onLater: () => void;
  /** Sends the anonymous pulse to the server; omitted in fixture mode. */
  onSignal?: () => Promise<unknown>;
}

export function ConstellationDrop({ constellation, answerText, onEnter, onLater, onSignal }: ConstellationDropProps) {
  const reduced = usePrefersReducedMotion();
  const [phase, setPhase] = useState<Phase>("ready");
  const [pulses, setPulses] = useState(0); // pulses from others: a count only, never who
  const headingRef = useRef<HTMLHeadingElement>(null);
  const chime = useChime();
  const members = constellation.memberCount ?? constellation.starIndices.length;
  const others = Math.min(MAX_OTHERS, Math.max(MIN_OTHERS, members - 1));
  const stars = useMemo(() => layout(constellation.constellationId, others), [constellation.constellationId, others]);
  const me = { x: 50, y: 50 };

  // Focus management: return focus to whatever opened the Drop when it closes.
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    return () => previous?.focus?.();
  }, []);
  useEffect(() => headingRef.current?.focus(), [phase]);

  useEffect(() => {
    if (phase !== "forming") return;
    const t = window.setTimeout(() => {
      setPhase("payoff");
      chime.play(659.25);
    }, reduced ? 0 : FORM_MS);
    return () => window.clearTimeout(t);
  }, [phase, reduced]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onLater();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onLater]);

  const start = () => {
    chime.play(392);
    setPhase("forming");
  };
  const signal = () => {
    chime.play(783.99);
    setPhase("signaled");
    void onSignal?.()
      ?.then((r) => {
        const n = (r as { pulses?: number } | undefined)?.pulses;
        if (typeof n === "number") setPulses(Math.max(0, n - 1)); // minus my own
      })
      .catch(() => undefined); // best effort; the moment never blocks
  };

  const showMeaning = members >= SHARED_MEANING_MIN && !!constellation.sharedMeaning;
  const ev = constellation.museEvidence;
  const evidenceLabel = constellation.isFallback
    ? "Fallback grouping"
    : ev
      ? `${ev.model} · Semantic grouping · ${ev.latencyMs} ms`
      : "Muse Spark · Semantic";
  const formed = phase === "payoff" || phase === "signaled";
  const announce =
    phase === "ready"
      ? "Your constellation is ready."
      : phase === "forming"
        ? "Stars are gathering around yours."
        : phase === "payoff"
          ? `You were not the only one. ${members} people landed together.`
          : "Signal sent. Your room is open for 24 hours.";

  return (
    <div className="spc-drop" role="dialog" aria-modal="true" aria-labelledby="spc-drop-title" data-testid="spc-drop" data-phase={phase}>
      <p className="spc-drop-sr" role="status" aria-live="polite">{announce}</p>
      <button
        type="button"
        className="spc-drop-sound"
        aria-pressed={chime.on}
        aria-label={chime.on ? "Mute chime" : "Play a soft chime"}
        onClick={() => chime.setOn(!chime.on)}
      >
        {chime.on ? <Volume2 size={18} aria-hidden="true" /> : <VolumeX size={18} aria-hidden="true" />}
      </button>

      <svg className={`spc-drop-sky${phase === "forming" ? " is-forming" : ""}${formed ? " is-formed" : ""}`} viewBox="0 0 100 100" preserveAspectRatio="xMidYMid meet" aria-hidden="true">
        {phase !== "ready" &&
          stars.map((s, i) => (
            <path key={`l${i}`} className="spc-drop-line" d={sketchPath(me, s, i % 2 ? 0.08 : -0.07)} pathLength={1} style={{ animationDelay: `${s.delay + 1300}ms` }} />
          ))}
        {phase !== "ready" && stars.length > 1 &&
          stars.map((s, i) => {
            const n = stars[(i + 1) % stars.length];
            return <path key={`r${i}`} className="spc-drop-line is-rim" d={sketchPath(s, n, 0.06)} pathLength={1} style={{ animationDelay: `${s.delay + 1900}ms` }} />;
          })}
        {phase !== "ready" && <path className="spc-drop-pulse" d={stars.map((s, i) => sketchPath(i ? stars[i - 1] : me, s, 0.04)).join(" ")} pathLength={1} />}
        {phase !== "ready" &&
          stars.map((s, i) => (
            <circle
              key={i}
              className="spc-drop-star"
              cx={s.x}
              cy={s.y}
              r={s.r}
              style={{ ["--fx" as string]: `${s.fromX - (s.x - 50)}px`, ["--fy" as string]: `${s.fromY - (s.y - 50)}px`, animationDelay: `${s.delay}ms` }}
            />
          ))}
        {phase === "signaled" &&
          stars.slice(0, Math.min(pulses, stars.length)).map((s, i) => (
            <circle key={`p${i}`} className="spc-drop-ring" cx={s.x} cy={s.y} r={s.r} style={{ animationDelay: `${400 + i * 420}ms` }} />
          ))}
        <circle className={`spc-drop-me${phase === "signaled" ? " is-signal" : ""}`} cx={me.x} cy={me.y} r={1.3} />
        <circle className="spc-drop-me-halo" cx={me.x} cy={me.y} r={3.4} />
      </svg>

      <div className="spc-drop-copy">
        {phase === "ready" && (
          <>
            <h2 id="spc-drop-title" ref={headingRef} tabIndex={-1}>Your constellation is ready</h2>
            <figure className="spc-drop-you">
              <img src={currentUser.avatar} alt="" width={36} height={36} />
              <figcaption>
                <span>Your star</span>
                <q>{answerText}</q>
              </figcaption>
            </figure>
            <div className="spc-drop-actions">
              <button type="button" className="spc-drop-btn is-primary" onClick={start}>See who landed with you</button>
              <button type="button" className="spc-drop-btn" onClick={onLater} data-testid="spc-drop-later">Later</button>
            </div>
          </>
        )}
        {phase === "forming" && (
          <h2 id="spc-drop-title" ref={headingRef} tabIndex={-1} className="spc-drop-quiet">Stars are finding yours</h2>
        )}
        {formed && (
          <>
            <h2 id="spc-drop-title" ref={headingRef} tabIndex={-1}>You were not the only one.</h2>
            <p className="spc-drop-count">{members >= SHARED_MEANING_MIN ? `${members} people here have been feeling this too.` : "You were not the only one today."}</p>
            <p className="spc-drop-meaning">{showMeaning ? constellation.sharedMeaning : "You were not the only one today."}</p>
            <p className={`spc-drop-chip${constellation.isFallback ? " is-fallback" : ""}`} data-testid="spc-drop-evidence">{evidenceLabel}</p>
            {phase === "payoff" ? (
              <div className="spc-drop-actions">
                <button type="button" className="spc-drop-btn is-primary" onClick={signal} data-testid="spc-drop-signal">Send a quiet signal</button>
                <button type="button" className="spc-drop-btn" onClick={onLater} data-testid="spc-drop-later">Not now</button>
              </div>
            ) : (
              <>
                <p className="spc-drop-note">Your constellation felt that. Your anonymous room is open for 24 hours.</p>
                <div className="spc-drop-actions">
                  <button type="button" className="spc-drop-btn is-primary" onClick={onEnter} data-testid="spc-drop-enter">Enter the room</button>
                  <button type="button" className="spc-drop-btn" onClick={onLater} data-testid="spc-drop-later">Not now</button>
                </div>
              </>
            )}
          </>
        )}
      </div>
    </div>
  );
}

/** Finds the newest closed day with a ready constellation and shows the Drop once per session. */
export function DropGate({
  client,
  cycleId,
  day,
  answerText,
  onEnter,
}: {
  client: CycleClient;
  cycleId: string | null;
  day: CycleDay | null;
  answerText: string;
  onEnter: () => void;
}) {
  const [found, setFound] = useState<DailyConstellation | null>(null);
  const [closed, setClosed] = useState(false);
  useEffect(() => {
    if (!cycleId || !day || !client.v3) return;
    const controller = new AbortController();
    client.v3.dailyConstellations(cycleId, day, controller.signal).then(
      (v) => {
        const c = v.placement === "pending" ? null : v.constellations[0] ?? null;
        if (!controller.signal.aborted) setFound(c && !isDismissed(c.constellationId) ? c : null);
      },
      () => !controller.signal.aborted && setFound(null),
    );
    return () => controller.abort();
  }, [client, cycleId, day]);

  if (!found || closed) return null;
  const finish = (after?: () => void) => {
    markDismissed(found.constellationId);
    setClosed(true);
    after?.();
  };
  return <ConstellationDrop constellation={found} answerText={answerText} onLater={() => finish()} onEnter={() => finish(onEnter)}
    onSignal={client.v3 && client.mode !== "fixture" ? () => client.v3!.sendQuietSignal(cycleId!, found.constellationId) : undefined} />;
}
