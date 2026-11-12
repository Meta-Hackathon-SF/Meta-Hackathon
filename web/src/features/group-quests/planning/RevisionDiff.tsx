import { ArrowRight, TriangleAlert } from "lucide-react";
import { diffPlans } from "./format";
import type { PublicPlanCard } from "./types";

interface RevisionDiffProps {
  previous: PublicPlanCard;
  current: PublicPlanCard;
  /** Optional public reason written by the server, e.g. "A member's availability changed." */
  reason?: string;
}

export default function RevisionDiff({ previous, current, reason }: RevisionDiffProps) {
  const changes = diffPlans(previous, current);
  const material = changes.some((c) => c.material);
  return (
    <section aria-label="What changed" className="rounded-lg border border-amber-200 bg-amber-50/60 p-3">
      <div className="flex items-start gap-2">
        <TriangleAlert aria-hidden className="mt-0.5 size-4 shrink-0 text-amber-700" />
        <div className="min-w-0">
          <p className="text-sm font-semibold text-amber-950">
            Plan updated (revision {current.revision}
            {current.basedOnRevision !== null ? `, replaces ${current.basedOnRevision}` : ""})
          </p>
          {reason && <p className="text-sm text-amber-900">{reason}</p>}
          {material && (
            <p className="mt-1 text-sm text-amber-900">
              The time, place or cost changed, so everyone needs to confirm again. The earlier plan is not
              treated as accepted for these details.
            </p>
          )}
        </div>
      </div>
      {changes.length === 0 ? (
        <p className="mt-2 text-sm text-amber-900">No visible details changed.</p>
      ) : (
        <dl className="mt-2 space-y-1.5">
          {changes.map((c) => (
            <div key={c.field} className="grid grid-cols-[4.5rem_1fr] gap-2 text-sm">
              <dt className="font-medium text-amber-950">{c.label}</dt>
              <dd className="flex min-w-0 flex-wrap items-center gap-x-1.5 text-amber-950">
                <del className="text-amber-800/80">{c.before}</del>
                <ArrowRight aria-label="changed to" className="size-3.5 shrink-0" />
                <ins className="font-medium no-underline">{c.after}</ins>
              </dd>
            </div>
          ))}
        </dl>
      )}
    </section>
  );
}
