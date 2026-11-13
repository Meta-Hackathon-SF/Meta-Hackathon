/*
 * "Why this group" for a constellation, drawn as an EXAMPLE. The real reason
 * comes from formation (Rishi, Constellation.sharedMeaning, guarded) and the
 * reveal view (Kai). Shared Groups / friends / events as signals are proposal
 * D010 and need Patrik's consent toggle; nothing here reads them.
 */
import { CalendarDays, Check, MessageSquareText, UserCheck, UsersRound } from "lucide-react";

type SignalState = "on" | "needs-ok";
const SIGNALS: { label: string; detail: string; state: SignalState; Icon: typeof Check }[] = [
  { label: "Daily answers", detail: "What your answers meant, never the words", state: "on", Icon: MessageSquareText },
  { label: "Groups you're in", detail: "Shared Groups make a star a little brighter", state: "needs-ok", Icon: UsersRound },
  { label: "Events you're going to", detail: "Same events, more in common", state: "needs-ok", Icon: CalendarDays },
  { label: "Posts and comments", detail: "Topics you post about, never the text", state: "needs-ok", Icon: MessageSquareText },
];

export default function MatchReasons() {
  return (
    <section className="card cst-panel" aria-labelledby="cst-why-title" data-testid="cst-why">
      <header className="cst-panel-head">
        <div>
          <h2 id="cst-why-title">Why this group</h2>
          <p className="muted">Shown with your constellation on Sunday</p>
        </div>
        <span className="cst-label cst-label-warn">Example</span>
      </header>

      <blockquote className="cst-why-quote">
        <span className="cst-label">In common</span>
        You all find it easier to talk to people while doing something with your hands.
      </blockquote>

      <h3 className="cst-subhead">Connections</h3>
      <ul className="cst-why-list">
        <li>
          <span className="cst-icon-circle is-small" aria-hidden="true">
            <UsersRound size={14} />
          </span>
          <span>
            <strong>2 of your 4 stars</strong> are in a Group you're in
          </span>
        </li>
        <li>
          <span className="cst-icon-circle is-small" aria-hidden="true">
            <UserCheck size={14} />
          </span>
          <span>
            <strong>None</strong> are already your friends, so these are new people
          </span>
        </li>
        <li>
          <span className="cst-icon-circle is-small" aria-hidden="true">
            <CalendarDays size={14} />
          </span>
          <span>
            <strong>3 of you</strong> are interested in the same event this week
          </span>
        </li>
      </ul>
      <p className="cst-panel-note muted">Counts only. Which star shares what appears after you both choose to reveal.</p>

      <h3 className="cst-subhead">What Muse used</h3>
      <ul className="cst-signals">
        {SIGNALS.map(({ label, detail, state, Icon }) => (
          <li key={label} className={`is-${state}`}>
            <Icon size={16} aria-hidden="true" />
            <span>
              <strong>{label}</strong>
              <small className="muted">{detail}</small>
            </span>
            <span className={`cst-label${state === "needs-ok" ? " cst-label-warn" : ""}`}>{state === "on" ? "On" : "Needs your OK"}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}
