import { CalendarX2, LoaderCircle, MessageCircleQuestion, RotateCw, WifiOff } from "lucide-react";
import type { PlanStatusState } from "./types";

export interface PlanStatusPanelProps {
  state: PlanStatusState;
  onRetry?: () => void;
  /** needs_input: open the availability/intent editor (Will/Patrik own the form). */
  onProvideInput?: () => void;
  /** no_feasible_plan: let the person pick another slot or broaden soft preferences. */
  onAdjust?: () => void;
}

export default function PlanStatusPanel({ state, onRetry, onProvideInput, onAdjust }: PlanStatusPanelProps) {
  const base = "flex gap-3 rounded-xl bg-white p-4 shadow-[0_1px_2px_#0003]";
  const action =
    "mt-2 inline-flex items-center gap-1.5 rounded-lg bg-slate-100 px-3 py-1.5 text-sm font-semibold text-slate-800 hover:bg-slate-200 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-500";

  if (state.kind === "planning") {
    return (
      <div role="status" aria-live="polite" className={base}>
        <LoaderCircle aria-hidden className="size-5 shrink-0 animate-spin text-sky-600 motion-reduce:animate-none" />
        <div>
          <p className="font-semibold text-slate-900">Planning your quest…</p>
          <p className="text-sm text-slate-600">Muse is choosing a time and place that works for everyone. Nothing is booked yet.</p>
        </div>
      </div>
    );
  }
  if (state.kind === "needs_input") {
    return (
      <div role="status" aria-live="polite" className={base}>
        <MessageCircleQuestion aria-hidden className="size-5 shrink-0 text-amber-600" />
        <div>
          <p className="font-semibold text-slate-900">We need a bit more information</p>
          <p className="text-sm text-slate-700">{state.question}</p>
          {onProvideInput && (
            <button type="button" className={action} onClick={onProvideInput}>Update my availability</button>
          )}
        </div>
      </div>
    );
  }
  if (state.kind === "no_feasible_plan") {
    return (
      <div role="status" aria-live="polite" className={base}>
        <CalendarX2 aria-hidden className="size-5 shrink-0 text-slate-500" />
        <div>
          <p className="font-semibold text-slate-900">No plan fits right now</p>
          <p className="text-sm text-slate-700">{state.reason}</p>
          <p className="mt-1 text-sm text-slate-500">We won't loosen anyone's limits behind the scenes.</p>
          {onAdjust && (
            <button type="button" className={action} onClick={onAdjust}>Try another time</button>
          )}
        </div>
      </div>
    );
  }
  return (
    <div role="alert" className={base}>
      <WifiOff aria-hidden className="size-5 shrink-0 text-red-600" />
      <div>
        <p className="font-semibold text-slate-900">Planning didn't finish</p>
        <p className="text-sm text-slate-700">{state.message}</p>
        {state.requestId && <p className="mt-1 text-xs text-slate-500">Reference {state.requestId}</p>}
        {state.retryable && onRetry && (
          <button type="button" className={action} onClick={onRetry}>
            <RotateCw aria-hidden className="size-4" /> Try again
          </button>
        )}
      </div>
    </div>
  );
}
