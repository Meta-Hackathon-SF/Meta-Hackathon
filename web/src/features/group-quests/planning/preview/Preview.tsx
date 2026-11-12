// Dev-only fixture preview body (see main.tsx).
import { useState, type ReactNode } from "react";
import { ContinuationCard, EvidenceBadge, PlanProposalCard, PlanStatusPanel } from "..";
import type { PlanPhase } from "../types";
import { continuation, liveEvidenceExample, planRev1, planRev2 } from "./fixtures";

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="space-y-2">
      <h2 className="text-sm font-semibold tracking-wide text-slate-500 uppercase">{title}</h2>
      {children}
    </section>
  );
}

export default function Preview() {
  const [phase, setPhase] = useState<PlanPhase>("joining");
  const [choice, setChoice] = useState<"accept" | "decline" | null>(null);
  const [hostView, setHostView] = useState(true);
  const [hosted, setHosted] = useState(false);
  return (
    <main className="mx-auto max-w-xl space-y-6 px-4 py-6">
      <p role="note" className="rounded-lg bg-fuchsia-100 px-3 py-2 text-sm font-medium text-fuchsia-900">
        Fixture preview: synthetic data, scripted output, not live Muse or a real backend.
      </p>

      <Section title="Proposal">
        <div className="flex flex-wrap gap-2 text-sm">
          {(["joining", "confirming_plan", "confirmed"] as PlanPhase[]).map((p) => (
            <button key={p} type="button" onClick={() => { setPhase(p); setChoice(null); }}
              className={`rounded-full px-3 py-1 ${phase === p ? "bg-slate-800 text-white" : "bg-white text-slate-700"}`}>
              {p}
            </button>
          ))}
        </div>
        <PlanProposalCard plan={planRev1} phase={phase} acceptedCount={2} viewerChoice={choice}
          onAccept={() => setChoice("accept")} onDecline={() => setChoice("decline")} />
      </Section>

      <Section title="Revision needing reconfirmation">
        <PlanProposalCard plan={planRev2} previous={planRev1} phase="reconfirming" acceptedCount={3}
          revisionReason="A member's availability changed." onAccept={() => {}} onDecline={() => {}} />
      </Section>

      <Section title="Status states">
        <PlanStatusPanel state={{ kind: "planning" }} />
        <PlanStatusPanel state={{ kind: "needs_input", fields: ["availability"], question: "There's no time that works for everyone in the group right now. Could you share another time you're free?" }} onProvideInput={() => {}} />
        <PlanStatusPanel state={{ kind: "no_feasible_plan", reason: "No approved public venue is open during a time that works for the whole group." }} onAdjust={() => {}} />
        <PlanStatusPanel state={{ kind: "error", message: "Muse is unavailable right now. Nothing was booked.", retryable: true, requestId: "req-fixture-9" }} onRetry={() => {}} />
      </Section>

      <Section title="Next week (continuation)">
        <label className="flex items-center gap-2 text-sm text-slate-700">
          <input type="checkbox" checked={hostView} onChange={(e) => setHostView(e.target.checked)} /> View as suggested host
        </label>
        <ContinuationCard continuation={continuation} simulated viewerId={hostView ? "p-cy" : "p-ava"} hostName="Cy (synthetic)"
          hostAccepted={hosted} onAcceptHost={() => setHosted(true)} />
      </Section>

      <Section title="Evidence labels">
        <div className="flex flex-wrap gap-2">
          <EvidenceBadge evidence={liveEvidenceExample} />
          <EvidenceBadge evidence={{ ...liveEvidenceExample, source: "replay" }} />
          <EvidenceBadge evidence={planRev1.evidence} />
        </div>
      </Section>
    </main>
  );
}

