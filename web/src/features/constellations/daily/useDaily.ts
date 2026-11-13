import { useCallback, useEffect, useRef, useState } from "react";
import { ClientError, type CurrentCycle, type CycleClient, type DailyAnswer, type DailyQuestion } from "./client";

export const DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"];
export const MAX_CHARS = 400;

export function message(error: unknown): string {
  if (error instanceof ClientError) {
    if (error.code === "CYCLE_LOCKED") return "This week is locked. Answers can no longer change.";
    if (error.code === "UNAUTHENTICATED") return "Join the group's Constellations game to answer.";
    if (error.code === "CONSENT_REQUIRED") return "Turn on all three consents to keep playing.";
    return error.message;
  }
  return "Something went wrong. Try again.";
}

export function when(iso: string): string {
  return new Date(iso).toLocaleString(undefined, { weekday: "long", hour: "numeric", minute: "2-digit" });
}

export interface Loaded {
  current: CurrentCycle | null;
  questions: DailyQuestion[];
  answers: DailyAnswer[];
  guess: number | null;
}

/** Loads the current week for the signed-in player; newer loads supersede older ones. */
export function useDaily(client: CycleClient) {
  const [data, setData] = useState<Loaded | null>(null);
  const [error, setError] = useState<string | null>(null);
  const request = useRef(0);

  const refresh = useCallback(async () => {
    const id = ++request.current;
    try {
      const current = await client.current();
      const [questions, answers, guess] = current
        ? await Promise.all([
            client.questions(current.cycle.cycleId),
            client.myAnswers(current.cycle.cycleId),
            client.myGuess(current.cycle.cycleId),
          ])
        : [[], [], null];
      if (id !== request.current) return;
      setData({ current, questions, answers, guess });
      setError(null);
    } catch (err) {
      if (id !== request.current) return;
      setError(message(err));
    }
  }, [client]);

  useEffect(() => {
    const counter = request;
    void refresh();
    const unsubscribe = client.subscribe(() => void refresh());
    return () => {
      counter.current++;
      unsubscribe();
    };
  }, [client, refresh]);

  return { data, error, refresh };
}
