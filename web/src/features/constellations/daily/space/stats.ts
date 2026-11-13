import { useEffect, useState } from "react";
import type { CycleClient, CycleDay } from "../client";

// ---------------------------------------------------------------- shared count hook
/** answeredToday from the v3 port. It only answers for a day you answered; null otherwise. */
export function useAnsweredToday(client: CycleClient, cycleId: string | null, day: CycleDay | null, answerId: string | null) {
  const [result, setResult] = useState<{ key: string; count: number } | null>(null);
  const key = cycleId && day && answerId ? `${cycleId}:${day}:${answerId}` : null;
  useEffect(() => {
    if (!key || !cycleId || !day || !client.v3) return;
    const controller = new AbortController();
    client.v3.dailyConstellations(cycleId, day, controller.signal).then(
      (v) => !controller.signal.aborted && setResult({ key, count: v.answeredToday }),
      () => {},
    );
    return () => controller.abort();
  }, [key, cycleId, day, client]);
  return result && result.key === key ? result.count : null;
}

// ---------------------------------------------------------------- own thinking time (this browser only)
const tookKey = (cycleId: string, day: number) => `spc-took:${cycleId}:${day}`;
export function readTook(cycleId: string, day: number): number | null {
  try {
    const v = Number(localStorage.getItem(tookKey(cycleId, day)));
    return Number.isFinite(v) && v > 0 ? v : null;
  } catch {
    return null;
  }
}
export function writeTook(cycleId: string, day: number, seconds: number) {
  try {
    localStorage.setItem(tookKey(cycleId, day), String(Math.round(seconds)));
  } catch {
    /* storage unavailable */
  }
}
export const fmtDuration = (s: number) => (s < 60 ? `${Math.round(s)}s` : `${Math.floor(s / 60)}m ${String(Math.round(s % 60)).padStart(2, "0")}s`);

