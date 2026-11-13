import { useCallback, useEffect, useRef, useState } from "react";
import { PrivacyError, type PrivacyClient, type SessionView } from "./client";

export type PrivacyState =
  | { status: "loading" }
  | { status: "signed_out" }
  | { status: "ready"; view: SessionView }
  | { status: "error"; message: string; retryable: boolean };

/** Loads this Group's session. Superseded loads are aborted and their results ignored. */
export function usePrivacySession(client: PrivacyClient, communityId: string) {
  const [state, setState] = useState<PrivacyState>({ status: "loading" });
  const seq = useRef(0);
  const inflight = useRef<AbortController | null>(null);

  const load = useCallback(() => {
    const id = ++seq.current;
    inflight.current?.abort();
    const controller = new AbortController();
    inflight.current = controller;
    client.session(communityId, controller.signal).then(
      (view) => {
        if (id === seq.current) setState(view ? { status: "ready", view } : { status: "signed_out" });
      },
      (error: unknown) => {
        if (id !== seq.current || (error as Error).name === "AbortError") return;
        const e = error instanceof PrivacyError ? error : null;
        setState({ status: "error", message: e?.message ?? "Something went wrong.", retryable: e?.retryable ?? true });
      },
    );
  }, [client, communityId]);

  useEffect(() => {
    load();
    return () => inflight.current?.abort();
  }, [load]);

  const set = useCallback((view: SessionView | null) => {
    seq.current++; // a local result supersedes any load still in flight
    inflight.current?.abort();
    setState(view ? { status: "ready", view } : { status: "signed_out" });
  }, []);

  return { state, reload: load, set };
}
