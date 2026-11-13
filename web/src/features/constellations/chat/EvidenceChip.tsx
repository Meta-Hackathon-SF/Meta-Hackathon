import type { MuseCallEvidence } from "../../../../../contracts/protocol";
import { parseEvidence } from "./runtime";

export function EvidenceChip({
  evidence,
  fixture = false,
}: {
  evidence?: MuseCallEvidence;
  fixture?: boolean;
}) {
  if (fixture)
    return (
      <small className="cst-chip">Synthetic fixture | No model call</small>
    );
  if (!evidence) return null;
  const e = parseEvidence(evidence);
  return (
    <small className="cst-chip">
      {e.source === "replay" ? "Replay of a saved cycle" : "Live"} | {e.model} |{" "}
      {e.callType} | {(e.latencyMs / 1000).toFixed(1)}s
    </small>
  );
}
