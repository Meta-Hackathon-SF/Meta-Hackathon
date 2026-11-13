import { useEffect, useMemo, useState, useSyncExternalStore } from "react";
import type { ReactNode } from "react";
import type { MuseCallEvidence } from "../../../../../contracts/protocol";
import { ChatPanel } from "./ChatPanel";
import { createChatClient } from "./client";
import { LiveChatSession } from "./LiveSession";
import { SkyPanel } from "../sky/SkyPanel";

export interface LiveConstellationProps {
  cycleId: string;
  viewerPlayerId: string; // From verified self-session; local filtering only, never sent as auth.
  baseUrl?: string;
  messageEvidence?: Record<string, MuseCallEvidence>;
  nudgeSlot?: ReactNode;
  projector?: boolean;
  demoTiming?: boolean; // Display only, sourced from the verified WeeklyCycle.
}

/** Will mounts this behind the existing verified privacy gate. No fixture mode. */
export function LiveConstellation(props: LiveConstellationProps) {
  const [attempt, setAttempt] = useState(0);
  return (
    <LiveView
      key={`${props.baseUrl ?? "/api/v1"}:${props.cycleId}:${props.viewerPlayerId}:${attempt}`}
      {...props}
      retry={() => setAttempt((value) => value + 1)}
    />
  );
}
function LiveView(props: LiveConstellationProps & { retry(): void }) {
  const client = useMemo(
    () => createChatClient({ baseUrl: props.baseUrl }),
    [props.baseUrl],
  );
  const session = useMemo(
    () => new LiveChatSession(client, props.cycleId, props.viewerPlayerId),
    [client, props.cycleId, props.viewerPlayerId],
  );
  const snapshot = useSyncExternalStore(
    session.subscribe,
    session.getSnapshot,
    session.getSnapshot,
  );
  useEffect(() => {
    session.start();
    return () => session.stop();
  }, [session]);
  return (
    <div className="cst-live" aria-label="Constellation and Sky">
      {props.demoTiming && (
        <p className="cst-notice">
          Demo timing | Eligible counts may include labeled synthetic players.
        </p>
      )}
      <p className="cst-muted" role="status">
        {snapshot.status === "connected"
          ? "Chat connection established"
          : snapshot.status === "unavailable"
            ? "Chat connection unavailable"
            : snapshot.status === "reconnecting"
              ? "Reconnecting to chat"
              : "Connecting to chat"}
      </p>
      {snapshot.notice && <p role="status">{snapshot.notice}</p>}
      {snapshot.room && (
        <ChatPanel
          room={snapshot.room}
          messages={snapshot.messages}
          actions={session.actions(snapshot.room.roomId)}
          mutualReveals={snapshot.reveals}
          messageEvidence={props.messageEvidence}
          nudgeSlot={props.nudgeSlot}
        />
      )}
      {snapshot.sky && (
        <SkyPanel sky={snapshot.sky} projector={props.projector} />
      )}
      <button type="button" onClick={props.retry}>
        Reconnect chat
      </button>
    </div>
  );
}
