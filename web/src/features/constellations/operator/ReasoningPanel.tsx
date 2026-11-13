/* "Muse proposes, code enforces": the operator view of Adam's reasoning trace. */
import { useEffect, useState } from "react";
import { ShieldCheck } from "lucide-react";
import { ClientError, type CycleClient } from "../daily/client";
import type { ReasoningEntry } from "./reasoning";

const OK = new Set(["ok", "kept", "accepted", "passed"]);

export default function ReasoningPanel({ client }: { client: CycleClient }) {
  const [rows, setRows] = useState<ReasoningEntry[] | string>("Loading…");
  useEffect(() => {
    if (!client.reasoning) return;
    const controller = new AbortController();
    client.reasoning(controller.signal).then(
      (value) => !controller.signal.aborted && setRows(value),
      (err: unknown) =>
        !controller.signal.aborted &&
        setRows(
          err instanceof ClientError && err.code === "NOT_FOUND"
            ? "Not available yet: the server hasn't mounted the reasoning trace."
            : "Not available right now.",
        ),
    );
    return () => controller.abort();
  }, [client]);
  if (!client.reasoning) return null;

  return (
    <section className="card cst-panel" aria-labelledby="cst-op-reasoning" data-testid="cst-op-reasoning">
      <h2 id="cst-op-reasoning" className="cst-card-title">
        <ShieldCheck size={18} aria-hidden="true" /> Muse proposes, code enforces
      </h2>
      <p className="cst-hint">Each Muse call and what server code did with its output. Codes and counts only, never prompts or answers.</p>
      {typeof rows === "string" ? (
        <p className="cst-hint">{rows}</p>
      ) : rows.length === 0 ? (
        <p className="cst-hint">{client.mode === "fixture" ? "None. Fixture mode never calls Muse." : "No calls recorded yet."}</p>
      ) : (
        <ul className="cst-reasoning">
          {rows.slice(0, 20).map((r) => (
            <li key={r.requestId}>
              <div className="cst-reasoning-call">
                <strong>{r.callType ?? r.task ?? "call"}</strong>
                <span className="cst-label">
                  {r.model ?? "model?"} · {r.latencyMs !== null ? `${Math.round(r.latencyMs)} ms` : "–"}
                </span>
                {r.source !== "live" && <span className="cst-label cst-label-warn">Replay of a saved round</span>}
                <span className={`cst-label ${r.outcome && OK.has(r.outcome) ? "is-ok" : "is-bad"}`}>{r.outcome ?? "pending"}</span>
              </div>
              {r.checks.length > 0 && (
                <ol className="cst-reasoning-checks" aria-label="Code checks">
                  {r.checks.map((c, i) => (
                    <li key={i}>
                      {c.stage}: {c.code}
                      {c.count > 1 ? ` ×${c.count}` : ""}
                    </li>
                  ))}
                </ol>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
