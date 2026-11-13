/*
 * Constellation Drop: shown once after a day closes and the player's constellation is ready.
 * It draws that day's sky with the shared SkyRenderer (same stars as the daily and week screens)
 * and finds the constellation outward from the player's own star. Other stars stay anonymous.
 */
import { useEffect, useMemo, useRef, useState } from "react";
import type { CycleClient, CycleDay } from "../client";
import type { DailyConstellation } from "../v3";
import { DAY_LONG } from "./model";
import SkyCanvas from "./SkyCanvas";
import "./drop.css";

type Phase = "ready" | "finding" | "found" | "signaled";

/** R2: nothing under 3 members is ever shown as a count or a meaning. */
const MIN_SHOWN = 3;

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

export interface ConstellationDropProps {
  constellation: DailyConstellation;
  day: CycleDay;
  /** Opens that day's sky. */
  onEnter: () => void;
  onLater: () => void;
  /** Sends the anonymous pulse to the server; omitted in fixture mode. */
  onSignal?: () => Promise<unknown>;
}

export function ConstellationDrop({ constellation, day, onEnter, onLater, onSignal }: ConstellationDropProps) {
  const [phase, setPhase] = useState<Phase>("ready");
  const [pulses, setPulses] = useState(0); // pulses from others: a count only, never who
  const headingRef = useRef<HTMLHeadingElement>(null);
  const members = constellation.memberCount ?? constellation.starIndices.length;
  const counted = members >= MIN_SHOWN;
  const dayName = DAY_LONG[day - 1];
  const answered = useMemo(() => new Set<number>([day]), [day]);

  // Focus management: return focus to whatever opened the Drop when it closes.
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    return () => previous?.focus?.();
  }, []);
  useEffect(() => headingRef.current?.focus(), [phase]);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onLater();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onLater]);

  const signal = () => {
    setPhase("signaled");
    void onSignal?.()
      ?.then((r) => {
        const n = (r as { pulses?: number } | undefined)?.pulses;
        if (typeof n === "number") setPulses(Math.max(0, n - 1)); // minus my own
      })
      .catch(() => undefined); // best effort; the screen never blocks on it
  };

  const ev = constellation.museEvidence;
  const evidenceLabel = constellation.isFallback
    ? "Fallback grouping"
    : ev
      ? `${ev.model} · Semantic grouping · ${ev.latencyMs} ms`
      : "Muse Spark · Semantic";
  const found = phase === "found" || phase === "signaled";

  return (
    <div className="spc-drop" role="dialog" aria-modal="true" aria-labelledby="spc-drop-title" data-testid="spc-drop" data-phase={phase}>
      <SkyCanvas
        input={{ mode: "drop", answered, viewDay: day, emptyDay: phase === "ready", noMatch: false }}
        hooks={{ onSettled: () => setPhase((p) => (p === "finding" ? "found" : p)) }}
      />
      <div className="spc-stage-ui is-in">
        {phase === "ready" && (
          <>
            <h2 id="spc-drop-title" ref={headingRef} tabIndex={-1} className="spc-stage-h">
              {dayName}&apos;s sky is in
            </h2>
            <div className="spc-stage-sub">See who answered close to you.</div>
            <button type="button" className="spc-btn spc-btn-white spc-btn-lg" onClick={() => setPhase("finding")}>
              Show me
            </button>
            <button type="button" className="spc-btn spc-btn-glass spc-btn-lg" onClick={onLater} data-testid="spc-drop-later">
              Later
            </button>
          </>
        )}
        {phase === "finding" && (
          <h2 id="spc-drop-title" ref={headingRef} tabIndex={-1} className="spc-stage-sub" role="status">
            Looking outward from your star…
          </h2>
        )}
        {found && (
          <>
            {counted && (
              <div className="spc-big-num" aria-hidden="true">
                {members}
              </div>
            )}
            <h2 id="spc-drop-title" ref={headingRef} tabIndex={-1} className="spc-stage-sub">
              {counted ? (
                <>
                  <span className="sr-only">{members} </span>people answered close to you
                </>
              ) : (
                "You're in today's sky."
              )}
            </h2>
            {counted && constellation.sharedMeaning && <p className="spc-meaning">{constellation.sharedMeaning}</p>}
            <p className="spc-drop-chip" data-testid="spc-drop-evidence">
              {evidenceLabel}
            </p>
            {phase === "found" ? (
              <>
                <button type="button" className="spc-btn spc-btn-white spc-btn-lg" onClick={signal} data-testid="spc-drop-signal">
                  Send a quiet signal
                </button>
                <button type="button" className="spc-btn spc-btn-glass spc-btn-lg" onClick={onLater} data-testid="spc-drop-later">
                  Not now
                </button>
              </>
            ) : (
              <>
                <p className="spc-stage-note" role="status">
                  Sent. They see a pulse, not your name.{pulses > 0 ? ` ${pulses} ${pulses === 1 ? "other has" : "others have"} sent one too.` : ""}
                </p>
                <button type="button" className="spc-btn spc-btn-white spc-btn-lg" onClick={onEnter} data-testid="spc-drop-enter">
                  Open {dayName}&apos;s sky
                </button>
                <button type="button" className="spc-btn spc-btn-glass spc-btn-lg" onClick={onLater} data-testid="spc-drop-later">
                  Done
                </button>
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
  onEnter,
}: {
  client: CycleClient;
  cycleId: string | null;
  day: CycleDay | null;
  onEnter: (day: CycleDay) => void;
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

  if (!found || closed || !day) return null;
  const finish = (after?: () => void) => {
    markDismissed(found.constellationId);
    setClosed(true);
    after?.();
  };
  return (
    <ConstellationDrop
      constellation={found}
      day={day}
      onLater={() => finish()}
      onEnter={() => finish(() => onEnter(day))}
      onSignal={client.v3 && client.mode !== "fixture" ? () => client.v3!.sendQuietSignal(cycleId!, found.constellationId) : undefined}
    />
  );
}
