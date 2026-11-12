import { FastForward, Crown, Send } from "lucide-react";
import { useId, useState } from "react";
import EvidenceBadge from "./EvidenceBadge";
import type { Continuation, Id } from "./types";

export interface ContinuationCardProps {
  continuation: Continuation;
  /** True when produced after the labeled "next week" time skip. */
  simulated: boolean;
  viewerId: Id | null;
  /** Public display name of the suggested host, if any. */
  hostName?: string;
  /** Kai's explicit host acceptance; receives the (possibly edited) draft text. */
  onAcceptHost?: (invitationDraft: string) => void;
  hostAccepted?: boolean;
  busy?: boolean;
  error?: string | null;
}

export default function ContinuationCard({
  continuation,
  simulated,
  viewerId,
  hostName,
  onAcceptHost,
  hostAccepted = false,
  busy = false,
  error = null,
}: ContinuationCardProps) {
  const [draft, setDraft] = useState(continuation.invitationText);
  const draftId = useId();
  const isHost = viewerId !== null && viewerId === continuation.proposedHostId;
  return (
    <article aria-label="Next week's quest" className="overflow-hidden rounded-xl bg-white shadow-[0_1px_2px_#0003]">
      {simulated && (
        <p className="flex items-center gap-2 bg-indigo-600 px-4 py-1.5 text-sm font-medium text-white">
          <FastForward aria-hidden className="size-4" />
          Simulated time skip: one week later. No attendance is assumed.
        </p>
      )}
      <div className="space-y-3 p-4 sm:p-5">
        <div className="flex flex-wrap items-center gap-2">
          <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-700">Next quest idea</span>
          <EvidenceBadge evidence={continuation.evidence} />
        </div>
        <p className="text-lg font-semibold text-slate-950">{continuation.nextActivity}</p>

        <div className="flex items-center gap-2 text-sm text-slate-700">
          <Crown aria-hidden className="size-4 text-amber-500" />
          {continuation.proposedHostId === null
            ? "No one has offered to host yet."
            : isHost
              ? "You said you'd like to come back. Want to host this one?"
              : `Suggested host: ${hostName ?? "a group member"}`}
        </div>

        {isHost && !hostAccepted && (
          <div className="space-y-2">
            <label htmlFor={draftId} className="block text-sm font-medium text-slate-800">
              Invitation draft (edit before saving)
            </label>
            <textarea
              id={draftId}
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              maxLength={600}
              rows={3}
              className="w-full rounded-lg border border-slate-300 p-2.5 text-[15px] focus-visible:border-sky-500 focus-visible:outline-none"
            />
            <p className="text-xs text-slate-500">Saving creates a draft quest only. Nothing is sent until you choose to share it.</p>
            {error && <p role="alert" className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-800">{error}</p>}
            {onAcceptHost && (
              <button
                type="button"
                onClick={() => onAcceptHost(draft.trim())}
                disabled={busy || draft.trim().length < 10}
                aria-busy={busy}
                className="inline-flex items-center gap-1.5 rounded-lg bg-[#0866ff] px-4 py-2 font-semibold text-white hover:bg-[#0759e0] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#0866ff]"
              >
                <Send aria-hidden className="size-4" />
                {busy ? "Saving…" : "Host it and save draft"}
              </button>
            )}
          </div>
        )}
        {hostAccepted && (
          <p role="status" className="text-sm font-medium text-emerald-700">You're hosting. Your draft invitation is saved.</p>
        )}
        {!isHost && (
          <blockquote className="border-l-2 border-slate-200 pl-3 text-sm text-slate-600">{continuation.invitationText}</blockquote>
        )}
      </div>
    </article>
  );
}
