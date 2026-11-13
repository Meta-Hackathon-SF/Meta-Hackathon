/*
 * Hosted app: the Sunday constellation in Messenger is a view of the real room.
 * Messages come from and go to the server room, so every member sees them on
 * their own account. A member's name shows only after a mutual reveal; everyone
 * else stays a star. Muse suggestions are shown only to the person who asked
 * (they are not posted to the room) and say so.
 */
import { useEffect, useMemo, useRef, useState } from "react";
import { Users } from "lucide-react";
import type { ChatMessage } from "../../../../../contracts/protocol";
import { getPrivacyClient, usePrivacySession } from "../privacy";
import { PLAY_COMMUNITY } from "../daily/communities";
import { useRoomNames } from "../daily/space/roomNames";
import { useRoom } from "../daily/space/useRoom";
import { addMuseMessage, type InboxMessage, type InboxThread } from "./inbox";
import { MessageCards } from "./MessageCards";
import { anonymize, askMuse, inferKind, type MuseKind } from "./museHelp";

const key = () => `m-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
const ERRORS: Record<string, string> = {
  MESSAGE_REJECTED: "Message not sent. Keep contact details and private answers out of chat.",
  ROOM_EXPIRED: "This room has closed.",
  RATE_LIMITED: "Wait a moment before sending another message.",
};

type Line = { at: string; live?: ChatMessage; local?: InboxMessage };

export function LiveGroupThread({ thread, suggestions }: { thread: InboxThread; suggestions: [MuseKind, string, string][] }) {
  const { state } = usePrivacySession(getPrivacyClient(), PLAY_COMMUNITY);
  const viewer = state.status === "ready" ? state.view.player.playerId : "";
  const { snapshot, actions, live } = useRoom(thread.live!.cycleId, viewer, Boolean(viewer));
  const room = snapshot.room;
  const { names } = useRoomNames(room, snapshot.reveals, actions, viewer);
  const [draft, setDraft] = useState("");
  const [note, setNote] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [asking, setAsking] = useState(false);
  const input = useRef<HTMLInputElement | null>(null);
  const end = useRef<HTMLDivElement | null>(null);

  const self = room?.members.find((m) => m.isSelf);
  const label = (handle: string) => names[handle]?.displayName ?? handle;
  const lines: Line[] = useMemo(() => {
    const out: Line[] = [];
    for (const m of snapshot.messages)
      if (m.roomId === room?.roomId && m.moderation === "visible" && m.kind !== "muse_nudge") out.push({ at: m.createdAt, live: m });
    for (const m of thread.messages) out.push({ at: m.at ?? "", local: m });
    return out.sort((a, b) => a.at.localeCompare(b.at));
  }, [snapshot.messages, thread.messages, room?.roomId]);
  useEffect(() => {
    end.current?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [lines.length, asking]);

  const members = room?.members.filter((m) => !m.isSelf).map((m) => label(m.handle)) ?? [];
  const status = !viewer
    ? "Join Facebook Space to see this chat."
    : !live
      ? "This chat needs the live server."
      : room?.status === "expired"
        ? "This room has closed."
        : !room
          ? (snapshot.notice ?? "Connecting to your constellation…")
          : null;

  const submit = async () => {
    const text = draft.trim();
    if (!text || busy || !actions || !room) return;
    const wantsMuse = /@muse\b/i.test(text);
    // The room gets the words without "@muse": the chat filter treats "@" as contact info.
    const forRoom = text.replace(/@muse\b/gi, "").replace(/\s{2,}/g, " ").trim();
    setBusy(true);
    setNote(null);
    try {
      if (forRoom) await actions.send(forRoom, { key: key(), signal: new AbortController().signal });
      setDraft("");
    } catch (error) {
      const code = error && typeof error === "object" && "code" in error ? String(error.code) : "";
      setNote(ERRORS[code] ?? "The message didn't send. Try again.");
      setBusy(false);
      return;
    }
    setBusy(false);
    if (!wantsMuse) return;
    const context = anonymize([
      ...lines.map((l) =>
        l.live
          ? { sender: l.live.handle, text: l.live.text, mine: l.live.handle === self?.handle, fromMuse: false }
          : { sender: l.local!.senderName, text: l.local!.text, mine: l.local!.mine, fromMuse: Boolean(l.local!.fromMuse) },
      ),
      { sender: "You", text, mine: true, fromMuse: false },
    ]);
    setAsking(true);
    const help = await askMuse(inferKind(text), context);
    addMuseMessage(thread.id, help);
    setAsking(false);
  };

  return (
    <div className="conversation" role="region" aria-label={thread.title} data-testid="live-group-thread">
      <header>
        <span className="avatar group-chip" aria-hidden="true">
          <Users size={18} />
        </span>
        <span>
          <strong>{thread.title}</strong>
          <small>{members.length ? `${members.join(", ")} · names show after a mutual reveal` : "Your constellation"}</small>
        </span>
      </header>
      <div className="conversation-body">
        {status && <p className="muted">{status}</p>}
        {lines.map((l) =>
          l.live ? (
            <div key={l.live.messageId} className="thread-line">
              {l.live.handle !== self?.handle && (
                <small className="thread-sender">{l.live.kind === "system" ? "Facebook Space" : label(l.live.handle)}</small>
              )}
              <p className={l.live.handle === self?.handle ? "sent-message" : "received-message"}>{l.live.text}</p>
            </div>
          ) : (
            <div key={l.local!.id} className="thread-line">
              {!l.local!.mine && (
                <small className="thread-sender">
                  {l.local!.fromMuse ? `${l.local!.source === "catalog" ? "Muse · catalog" : "Muse"} · only you see this` : l.local!.senderName}
                </small>
              )}
              <p className={l.local!.mine ? "sent-message" : l.local!.fromMuse ? "muse-message" : "received-message"}>{l.local!.text}</p>
              <MessageCards threadId={thread.id} message={l.local!} />
            </div>
          ),
        )}
        {asking && <p className="muted">Muse is writing…</p>}
        <div ref={end} />
      </div>
      {note && (
        <p className="spc-error" role="alert">
          {note}
        </p>
      )}
      <div className="muse-actions" role="group" aria-label="Ask Muse">
        <span className="muse-hint">Mention @muse for ideas (only you see Muse's reply), or tap one:</span>
        {suggestions.map(([kind, text, fill]) => (
          <button
            key={kind}
            type="button"
            disabled={asking || !room}
            onClick={() => {
              setDraft(fill);
              input.current?.focus();
            }}
          >
            {text}
          </button>
        ))}
      </div>
      <form
        onSubmit={(event) => {
          event.preventDefault();
          void submit();
        }}
      >
        <input
          ref={input}
          aria-label="Message"
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          placeholder="Aa · mention @muse for ideas"
          maxLength={500}
          disabled={!room || room.status !== "open"}
        />
        <button type="submit" aria-label="Send message" disabled={!draft.trim() || busy || asking || !room}>
          Send
        </button>
      </form>
    </div>
  );
}
