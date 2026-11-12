import { useCallback, useEffect, useRef, useState } from "react";
import type { Id, IsoTime } from "../../../../../contracts/protocol";

/**
 * Measures confirmed intent -> persisted quest acceptance. This is a
 * measurement, not a countdown: it starts only when the server acknowledges a
 * confirmed intent and completes only when an acceptance acknowledgement is
 * reported by the events component. Attempts that end otherwise are recorded
 * as abandoned, separately from completed ones.
 */
export interface TimerAttempt {
  attemptId: number;
  intentVersion: number;
  startedAt: IsoTime;
  outcome: "running" | "completed" | "abandoned";
  elapsedMs: number | null;
  questId: Id | null;
  abandonReason: string | null;
}

export interface AcceptanceAck {
  questId: Id;
  revision: number;
  /** Server timestamp of the persisted acceptance. */
  acceptedAt: IsoTime;
}

export function useFirstActionTimer(onFinished?: (attempt: TimerAttempt) => void) {
  const [attempts, setAttempts] = useState<TimerAttempt[]>([]);
  const [now, setNow] = useState(() => performance.now());
  const startedPerf = useRef<number | null>(null);
  const [runningSince, setRunningSince] = useState<number | null>(null);
  const seed = useRef(0);
  const attemptsRef = useRef<TimerAttempt[]>([]);
  const onFinishedRef = useRef(onFinished);
  useEffect(() => {
    onFinishedRef.current = onFinished;
  }, [onFinished]);

  const commit = useCallback((next: TimerAttempt[]) => {
    attemptsRef.current = next;
    setAttempts(next);
  }, []);

  const finish = useCallback(
    (patch: Partial<TimerAttempt> & Pick<TimerAttempt, "outcome">) => {
      const list = attemptsRef.current;
      const current = list[list.length - 1];
      if (!current || current.outcome !== "running" || startedPerf.current === null) return;
      const done: TimerAttempt = {
        ...current,
        ...patch,
        elapsedMs: Math.round(performance.now() - startedPerf.current),
      };
      startedPerf.current = null;
      setRunningSince(null);
      commit([...list.slice(0, -1), done]);
      onFinishedRef.current?.(done);
    },
    [commit],
  );

  const start = useCallback(
    (intentVersion: number) => {
      finish({ outcome: "abandoned", abandonReason: "restarted" });
      startedPerf.current = performance.now();
      setRunningSince(startedPerf.current);
      setNow(startedPerf.current);
      commit([
        ...attemptsRef.current,
        {
          attemptId: ++seed.current,
          intentVersion,
          startedAt: new Date().toISOString(),
          outcome: "running",
          elapsedMs: null,
          questId: null,
          abandonReason: null,
        },
      ]);
    },
    [commit, finish],
  );

  /** Call only with a server acknowledgement of a persisted acceptance. */
  const complete = useCallback(
    (ack: AcceptanceAck) => finish({ outcome: "completed", questId: ack.questId }),
    [finish],
  );
  const abandon = useCallback(
    (reason: string) => finish({ outcome: "abandoned", abandonReason: reason }),
    [finish],
  );

  const current = attempts[attempts.length - 1] ?? null;
  const running = current?.outcome === "running";
  useEffect(() => {
    if (!running) return;
    const id = window.setInterval(() => setNow(performance.now()), 1000);
    return () => window.clearInterval(id);
  }, [running]);

  // Leaving the feature mid-attempt is an abandonment.
  useEffect(() => () => finish({ outcome: "abandoned", abandonReason: "left_feature" }), [finish]);

  const elapsedMs =
    running && runningSince !== null ? Math.max(0, now - runningSince) : (current?.elapsedMs ?? null);
  return { attempts, current, elapsedMs, start, complete, abandon };
}

export function formatElapsed(ms: number | null): string {
  if (ms === null) return "--:--";
  const total = Math.floor(ms / 1000);
  return `${String(Math.floor(total / 60)).padStart(2, "0")}:${String(total % 60).padStart(2, "0")}`;
}
