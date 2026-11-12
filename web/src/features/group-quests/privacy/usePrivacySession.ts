import { useCallback, useEffect, useRef, useState } from "react";
import { PrivacyApiError } from "./client";
import type { PrivacyClient, SessionView } from "./client";

export type SessionState =
  | { status: "loading" }
  | { status: "signed_out" }
  | { status: "ready"; session: SessionView }
  | { status: "error"; error: PrivacyApiError };

/** Loads the server session. Superseded loads are aborted and ignored. */
export function usePrivacySession(client: PrivacyClient) {
  const [state, setState] = useState<SessionState>({ status: "loading" });
  const seq = useRef(0);
  const controller = useRef<AbortController | null>(null);

  const reload = useCallback(async () => {
    controller.current?.abort();
    const ac = new AbortController();
    controller.current = ac;
    const mine = ++seq.current;
    try {
      const session = await client.getSession(ac.signal);
      if (mine !== seq.current) return;
      setState(session ? { status: "ready", session } : { status: "signed_out" });
    } catch (error) {
      if (mine !== seq.current || (error as Error).name === "AbortError") return;
      setState({ status: "error", error: toApiError(error) });
    }
  }, [client]);

  const start = useCallback(async () => {
    const mine = ++seq.current;
    setState({ status: "loading" });
    try {
      const session = await client.startSession();
      if (mine === seq.current) setState({ status: "ready", session });
    } catch (error) {
      if (mine === seq.current) setState({ status: "error", error: toApiError(error) });
    }
  }, [client]);

  useEffect(() => {
    const ac = new AbortController();
    controller.current = ac;
    const mine = ++seq.current;
    client.getSession(ac.signal).then(
      (session) => {
        if (mine === seq.current) setState(session ? { status: "ready", session } : { status: "signed_out" });
      },
      (error) => {
        if (mine === seq.current && (error as Error).name !== "AbortError") setState({ status: "error", error: toApiError(error) });
      },
    );
    return () => ac.abort();
  }, [client]);

  return { state, reload, start };
}

export function toApiError(error: unknown): PrivacyApiError {
  return error instanceof PrivacyApiError
    ? error
    : new PrivacyApiError("NETWORK", "Something went wrong. Try again.", null, true);
}
