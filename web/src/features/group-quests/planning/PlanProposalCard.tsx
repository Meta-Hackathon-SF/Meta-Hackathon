import { CalendarClock, Check, MapPin, Puzzle, Users, Wallet } from "lucide-react";
import type { ReactNode } from "react";
import EvidenceBadge from "./EvidenceBadge";
import RevisionDiff from "./RevisionDiff";
import { durationMinutes, formatCost, formatWhen } from "./format";
import type { PlanPhase, PublicPlanCard } from "./types";

export interface PlanProposalCardProps {
  plan: PublicPlanCard;
  phase: PlanPhase;
  /** Previous revision; when present a before/after diff is shown. */
  previous?: PublicPlanCard | null;
  revisionReason?: string;
  acceptedCount?: number;
  minimumSize?: number;
  capacity?: number;
  viewerChoice?: "accept" | "decline" | null;
  onAccept?: () => void;
  onDecline?: () => void;
  busy?: boolean;
  error?: string | null;
}

const ACCEPT_LABEL: Record<PlanPhase, string> = {
  joining: "Join this quest",
  confirming_plan: "Confirm this plan",
  reconfirming: "Confirm new details",
  confirmed: "Confirmed",
};

const PHASE_HINT: Record<PlanPhase, string> = {
  joining: "Joining says you're interested. Final details are confirmed once enough people join.",
  confirming_plan: "These are the final details. Confirm if they work for you.",
  reconfirming: "Details changed since you accepted. Confirm again to stay on this quest.",
  confirmed: "You're confirmed for this plan.",
};

function Row({ icon, label, children }: { icon: ReactNode; label: string; children: ReactNode }) {
  return (
    <div className="flex gap-2.5">
      <span aria-hidden className="mt-0.5 text-slate-500">{icon}</span>
      <div className="min-w-0">
        <p className="text-xs font-medium tracking-wide text-slate-500 uppercase">{label}</p>
        <div className="text-[15px] text-slate-900">{children}</div>
      </div>
    </div>
  );
}

export default function PlanProposalCard({
  plan,
  phase,
  previous,
  revisionReason,
  acceptedCount,
  minimumSize = 3,
  capacity = 5,
  viewerChoice = null,
  onAccept,
  onDecline,
  busy = false,
  error = null,
}: PlanProposalCardProps) {
  const headingId = `gq-plan-${plan.planId}`;
  const minutes = durationMinutes(plan.start, plan.end);
  const decided = viewerChoice !== null || phase === "confirmed";
  return (
    <article aria-labelledby={headingId} className="overflow-hidden rounded-xl bg-white shadow-[0_1px_2px_#0003]">
      <div className="h-1.5 bg-gradient-to-r from-teal-500 via-sky-500 to-indigo-500" aria-hidden />
      <div className="space-y-4 p-4 sm:p-5">
        <header className="space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-700">
              Quest plan · rev {plan.revision}
            </span>
            <EvidenceBadge evidence={plan.evidence} />
          </div>
          <h3 id={headingId} className="text-xl leading-tight font-bold text-slate-950">{plan.title}</h3>
          <p className="text-[15px] text-slate-700">{plan.activity}</p>
        </header>

        {previous && <RevisionDiff previous={previous} current={plan} reason={revisionReason} />}

        <div className="rounded-lg bg-teal-50 p-3 ring-1 ring-teal-100">
          <Row icon={<Puzzle className="size-4" />} label="Do it together">
            {plan.collaborationTask}
          </Row>
        </div>

        <div className="grid gap-3 sm:grid-cols-2">
          <Row icon={<CalendarClock className="size-4" />} label="When">
            {formatWhen(plan.start, plan.end, plan.timeZone)}
            <span className="block text-sm text-slate-500">{minutes} minutes</span>
          </Row>
          <Row icon={<MapPin className="size-4" />} label="Where">
            {plan.venue.name}
            <span className="block text-sm text-slate-500">{plan.venue.publicAddress}</span>
          </Row>
          <Row icon={<Wallet className="size-4" />} label="Cost">
            {formatCost(plan.costPerPersonMinor, plan.currency)}
          </Row>
          {acceptedCount !== undefined && (
            <Row icon={<Users className="size-4" />} label="Group">
              {acceptedCount} of {capacity} spots
              <span className="block text-sm text-slate-500">
                {acceptedCount >= minimumSize ? "Enough people to go ahead" : `Needs ${minimumSize - acceptedCount} more to go ahead`}
              </span>
            </Row>
          )}
        </div>

        <p className="border-l-2 border-sky-300 pl-3 text-sm text-slate-600">
          <span className="font-medium text-slate-800">Why this plan: </span>
          {plan.publicRationale}
        </p>

        <footer className="space-y-2 border-t border-slate-100 pt-3">
          <p className="text-sm text-slate-600">{PHASE_HINT[phase]}</p>
          {error && (
            <p role="alert" className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-800">{error}</p>
          )}
          {decided ? (
            <p role="status" className="flex items-center gap-1.5 text-sm font-medium text-emerald-700">
              {viewerChoice === "decline" ? (
                "You passed on this plan."
              ) : (
                <>
                  <Check aria-hidden className="size-4" /> {phase === "confirmed" ? "You're in." : "Response recorded."}
                </>
              )}
            </p>
          ) : (
            (onAccept || onDecline) && (
              <div className="flex flex-wrap gap-2">
                {onAccept && (
                  <button
                    type="button"
                    onClick={onAccept}
                    disabled={busy}
                    aria-busy={busy}
                    className="rounded-lg bg-[#0866ff] px-4 py-2 font-semibold text-white hover:bg-[#0759e0] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#0866ff]"
                  >
                    {busy ? "Saving…" : ACCEPT_LABEL[phase]}
                  </button>
                )}
                {onDecline && (
                  <button
                    type="button"
                    onClick={onDecline}
                    disabled={busy}
                    className="rounded-lg bg-slate-100 px-4 py-2 font-semibold text-slate-800 hover:bg-slate-200 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-500"
                  >
                    Not this time
                  </button>
                )}
              </div>
            )
          )}
        </footer>
      </div>
    </article>
  );
}
