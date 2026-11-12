import { FlaskConical, History, Sparkles } from "lucide-react";
import { evidenceKind, evidenceLabel } from "./format";
import type { ModelEvidence } from "./types";

const STYLES = {
  live: "bg-emerald-50 text-emerald-800 ring-emerald-200",
  replay: "bg-amber-50 text-amber-900 ring-amber-300",
  fixture: "bg-fuchsia-50 text-fuchsia-900 ring-fuchsia-300",
} as const;

export default function EvidenceBadge({ evidence }: { evidence: ModelEvidence }) {
  const kind = evidenceKind(evidence);
  const Icon = kind === "live" ? Sparkles : kind === "replay" ? History : FlaskConical;
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset ${STYLES[kind]}`}
      title={`Generated ${new Date(evidence.generatedAt).toLocaleString()}`}
      data-evidence={kind}
    >
      <Icon aria-hidden className="size-3.5" />
      {evidenceLabel(evidence)}
    </span>
  );
}
