/*
 * "Why this group" (D010). With `context` it shows computed counts (fixture:
 * labeled Synthetic players; live: ChatRoom.context from the server). Without
 * it, a labeled EXAMPLE. Counts only: never which star shares what.
 * The signal list reflects the player's own "use my activity" switch.
 */
import { CalendarDays, Check, MessageSquareText, UserCheck, UsersRound } from "lucide-react";
import type { ConstellationContext } from "../../../../../contracts/protocol.ts";

const EXAMPLE: ConstellationContext = { sharedGroupStars: 2, alreadyFriends: 0, sameEventStars: 2 };

function count(n: number, total: number) {
  return n === 0 ? "None" : n === total ? `All ${total}` : `${n} of your ${total} stars`;
}

export default function MatchReasons({
  context,
  members = 4,
  activityOn = false,
  label,
}: {
  context?: ConstellationContext | null;
  members?: number;
  activityOn?: boolean;
  label?: string;
}) {
  const real = Boolean(context);
  const c = context ?? EXAMPLE;
  const signals: { label: string; detail: string; on: boolean; Icon: typeof Check }[] = [
    { label: "Daily answers", detail: "What your answers meant, never the words", on: true, Icon: MessageSquareText },
    { label: "Groups you're in", detail: "Shared Groups make a star a little brighter", on: activityOn, Icon: UsersRound },
    { label: "Events you're going to", detail: "Same events, more in common", on: activityOn, Icon: CalendarDays },
    { label: "Posts and comments", detail: "Topics you post about, never the text", on: activityOn, Icon: MessageSquareText },
  ];
  return (
    <section className="card cst-panel" aria-labelledby="cst-why-title" data-testid="cst-why">
      <header className="cst-panel-head">
        <div>
          <h2 id="cst-why-title">Why this group</h2>
          <p className="muted">Shown with your constellation on Sunday</p>
        </div>
        <span className="cst-label cst-label-warn">{real ? (label ?? "Synthetic players") : "Example"}</span>
      </header>

      <blockquote className="cst-why-quote">
        <span className="cst-label">In common</span>
        You all find it easier to talk to people while doing something with your hands.
      </blockquote>

      <h3 className="cst-subhead">Connections</h3>
      {real && !activityOn ? (
        <p className="cst-panel-note muted" data-testid="cst-why-off">
          Turn on "use my activity" in Privacy and data to see shared Groups, friends and events.
        </p>
      ) : (
        <ul className="cst-why-list">
          <li>
            <span className="cst-icon-circle is-small" aria-hidden="true">
              <UsersRound size={14} />
            </span>
            <span>
              <strong>{count(c.sharedGroupStars, members)}</strong> {c.sharedGroupStars === 1 ? "is" : "are"} in a Group you're in
            </span>
          </li>
          <li>
            <span className="cst-icon-circle is-small" aria-hidden="true">
              <UserCheck size={14} />
            </span>
            <span>
              <strong>{count(c.alreadyFriends, members)}</strong>{" "}
              {c.alreadyFriends === 0 ? "are already your friends, so these are new people" : "already your friends"}
            </span>
          </li>
          <li>
            <span className="cst-icon-circle is-small" aria-hidden="true">
              <CalendarDays size={14} />
            </span>
            <span>
              <strong>{count(c.sameEventStars, members)}</strong> {c.sameEventStars === 1 ? "is" : "are"} interested in an
              event you're interested in
            </span>
          </li>
        </ul>
      )}
      <p className="cst-panel-note muted">Counts only. Which star shares what appears after you both choose to reveal.</p>

      <h3 className="cst-subhead">What Muse used</h3>
      <ul className="cst-signals">
        {signals.map(({ label: name, detail, on, Icon }) => (
          <li key={name} className={on ? "is-on" : "is-off"}>
            <Icon size={16} aria-hidden="true" />
            <span>
              <strong>{name}</strong>
              <small className="muted">{detail}</small>
            </span>
            <span className={`cst-label${on ? "" : " cst-label-warn"}`}>{on ? "On" : "Off"}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}
