import { useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import type {
  ChatMessage,
  ChatRoom,
  MuseCallEvidence,
  MutualReveal,
  Report,
} from "../../../../../contracts/protocol";
import { EvidenceChip } from "./EvidenceChip";
import { ChatHttpError } from "./client";
import { SupportCard } from "../privacy";
import { object, oneOf, parseMessage, parseReveal, parseRoom } from "./runtime";
import "./chat.css";

export interface ActionContext {
  key: string;
  signal: AbortSignal;
}
export interface ChatActions {
  send(text: string, context: ActionContext): Promise<unknown>;
  report(
    messageId: string,
    handle: string,
    reason: Report["reason"],
    context: ActionContext,
  ): Promise<void>;
  block(handle: string, context: ActionContext): Promise<void>;
  reveal(toHandle: string, context: ActionContext): Promise<unknown>;
}
export interface ChatPanelProps {
  room: ChatRoom;
  messages: ChatMessage[];
  actions?: ChatActions;
  fixture?: boolean;
  fixtureNow?: number;
  mutualReveals?: MutualReveal[];
  messageEvidence?: Record<string, MuseCallEvidence>;
  nudgeSlot?: ReactNode;
}
const safeColor = (value: string) =>
  /^#[0-9a-f]{6}$/i.test(value) ? value : "#7c9cff";
function safeError(error: unknown): string {
  const code =
    error && typeof error === "object" && "code" in error ? error.code : "";
  if (code === "MESSAGE_REJECTED")
    return "Message not sent. Keep contact details and private answers out of chat.";
  if (code === "ROOM_EXPIRED")
    return "This room has expired. Messages are read-only.";
  if (code === "RATE_LIMITED")
    return "Please wait a moment before sending another message.";
  return "That action could not be completed. You can retry.";
}

export function ChatPanel(props: ChatPanelProps) {
  return <ChatSession key={props.room.roomId} {...props} />;
}

function ChatSession(props: ChatPanelProps) {
  const room = parseRoom(props.room);
  const [localMessages, setLocalMessages] = useState<
    { message: ChatMessage; source: ChatMessage[] }[]
  >([]);
  const serverMessages = props.messages.map(parseMessage);
  const ids = new Set(serverMessages.map((m) => m.messageId));
  const messages = [
    ...serverMessages,
    ...localMessages
      .filter(
        (m) => m.source === props.messages && !ids.has(m.message.messageId),
      )
      .map((m) => m.message),
  ];
  const [draft, setDraft] = useState("");
  const [hidden, setHidden] = useState<Set<string>>(new Set());
  const [blocked, setBlocked] = useState<Set<string>>(new Set());
  const [pending, setPending] = useState<Set<string>>(new Set());
  const [error, setError] = useState("");
  const [supportAvailable, setSupportAvailable] = useState(false);
  const [busy, setBusy] = useState(false);
  const [now, setNow] = useState(() => Date.now());
  const request = useRef<{ seq: number; controller?: AbortController }>({
    seq: 0,
  });
  const keys = useRef(new Map<string, string>());
  const [retry, setRetry] = useState<(() => void) | null>(null);
  const self = room.members.find((m) => m.isSelf);
  const viewNow =
    props.fixture && props.fixtureNow !== undefined ? props.fixtureNow : now;
  const expired =
    room.status !== "open" || viewNow >= Date.parse(room.expiresAt);
  const notOpen = viewNow < Date.parse(room.opensAt);
  const canWrite = !!props.actions && !!self && !expired && !notOpen;

  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, []);
  useEffect(() => {
    const state = request.current;
    return () => {
      state.controller?.abort();
      state.seq += 1;
    };
  }, []);

  async function perform(
    name: string,
    body: unknown,
    call: (context: ActionContext) => Promise<unknown>,
    done: (result: unknown) => void,
  ) {
    if (!canWrite || busy) return;
    const identity = JSON.stringify([room.roomId, name, body]);
    const key = keys.current.get(identity) ?? crypto.randomUUID();
    keys.current.set(identity, key);
    request.current.controller?.abort();
    const controller = new AbortController();
    const seq = ++request.current.seq;
    request.current.controller = controller;
    setBusy(true);
    setError("");
    if (name === "send") setSupportAvailable(false);
    setRetry(null);
    try {
      const result = await call({ key, signal: controller.signal });
      if (controller.signal.aborted || seq !== request.current.seq) return;
      done(result);
      keys.current.delete(identity);
    } catch (failure) {
      if (controller.signal.aborted || seq !== request.current.seq) return;
      const offerSupport =
        name === "send" &&
        failure instanceof ChatHttpError &&
        failure.code === "MESSAGE_REJECTED" &&
        failure.supportAvailable;
      if (name === "send") setSupportAvailable(offerSupport);
      setError(
        offerSupport
          ? "Your message was held. The support card below stays private."
          : safeError(failure),
      );
      setRetry(() => () => {
        void perform(name, body, call, done);
      });
    } finally {
      if (seq === request.current.seq) setBusy(false);
    }
  }
  function send() {
    if (!draft.trim() || draft.length > 500 || !props.actions) return;
    const text = draft;
    void perform(
      "send",
      { text },
      (ctx) => props.actions!.send(text, ctx),
      (value) => {
        const message = parseMessage(value);
        if (
          message.roomId !== room.roomId ||
          message.handle !== self?.handle ||
          message.kind !== "player" ||
          message.moderation !== "visible"
        )
          throw new Error("Invalid response");
        setLocalMessages((previous) =>
          previous.some((m) => m.message.messageId === message.messageId)
            ? previous
            : [...previous, { message, source: props.messages }],
        );
        setDraft((previous) => (previous === text ? "" : previous));
      },
    );
  }
  function report(message: ChatMessage) {
    setHidden((prev) => new Set([...prev, message.messageId]));
    void perform(
      "report",
      { messageId: message.messageId },
      (ctx) =>
        props.actions!.report(message.messageId, message.handle, "other", ctx),
      () => {},
    );
  }
  function block(handle: string) {
    setBlocked((prev) => new Set([...prev, handle]));
    void perform(
      "block",
      { handle },
      (ctx) => props.actions!.block(handle, ctx),
      () => {},
    );
  }
  function reveal(handle: string) {
    void perform(
      "reveal",
      { toHandle: handle },
      (ctx) => props.actions!.reveal(handle, ctx),
      (value) => {
        const result = object(value, ["result"]);
        oneOf(result.result, ["pending", "revealed"]);
        setPending((prev) => new Set([...prev, handle]));
      },
    );
  }
  const reveals =
    expired || notOpen
      ? []
      : (props.mutualReveals ?? [])
          .map(parseReveal)
          .filter((r) => r.roomId === room.roomId);
  return (
    <section className="cst-chat" aria-label="Anonymous constellation chat">
      <header className="cst-chat-header">
        <div>
          <p className="cst-eyebrow">Your constellation</p>
          <h2>A little less alone</h2>
        </div>
        <span className="cst-orbit" aria-hidden="true">
          &#10022;
        </span>
      </header>
      {props.fixture && (
        <p className="cst-notice">
          Synthetic player | Synthetic fixture | Demo timing. No live moderation
          or model call.
        </p>
      )}
      <p className="cst-muted">
        Your daily answers stay private. Here, you choose what to share.
      </p>
      <p className="cst-expiry" role="status">
        {expired
          ? "Room expired | Messages are read-only"
          : notOpen
            ? "This room has not opened yet"
            : `Chat closes ${new Date(room.expiresAt).toLocaleString("en-US", { timeZoneName: "short" })}`}
      </p>
      <ul className="cst-members" aria-label="Anonymous members">
        {room.members.map((m) => (
          <li key={m.handle}>
            <span
              className="cst-star"
              style={{ backgroundColor: safeColor(m.starColor) }}
              aria-hidden="true"
            />
            <span>
              {m.handle}
              {m.isSelf ? " (you)" : ""}
            </span>
            {!m.isSelf && !blocked.has(m.handle) && (
              <span className="cst-member-actions">
                <button
                  disabled={!canWrite || busy}
                  onClick={() => reveal(m.handle)}
                >
                  {pending.has(m.handle)
                    ? "Request sent"
                    : `Reveal with ${m.handle}`}
                </button>
                <button
                  disabled={!canWrite || busy}
                  onClick={() => block(m.handle)}
                >
                  Block {m.handle}
                </button>
              </span>
            )}
          </li>
        ))}
      </ul>
      {pending.size > 0 && (
        <p className="cst-muted" role="status">
          Identity stays private until you both choose to reveal.
        </p>
      )}
      {reveals.map((reveal) => (
        <aside
          className="cst-mutual"
          key={reveal.players.map((p) => p.playerId).join(":")}
        >
          <strong>Mutual reveal</strong>
          <p>
            {reveal.players
              .map(
                (p) =>
                  `${p.displayName}${p.isSynthetic ? " | Synthetic player" : ""}`,
              )
              .join(" & ")}
          </p>
        </aside>
      ))}
      <ol className="cst-messages" aria-label="Messages" aria-live="polite">
        {messages
          .filter(
            (m) =>
              m.roomId === room.roomId &&
              m.moderation === "visible" &&
              !hidden.has(m.messageId) &&
              !blocked.has(m.handle) &&
              (m.kind === "player" ||
                props.fixture ||
                props.messageEvidence?.[m.messageId]),
          )
          .map((m) => (
            <li
              key={m.messageId}
              className={m.handle === self?.handle ? "cst-own-message" : ""}
            >
              <div className="cst-message-meta">
                <strong>{m.handle}</strong>
                <time dateTime={m.createdAt}>
                  {new Date(m.createdAt).toLocaleTimeString([], {
                    hour: "2-digit",
                    minute: "2-digit",
                  })}
                </time>
              </div>
              <p>{m.text}</p>
              {m.kind !== "player" && (
                <EvidenceChip
                  evidence={props.messageEvidence?.[m.messageId]}
                  fixture={props.fixture}
                />
              )}
              {m.kind === "player" && m.handle !== self?.handle && (
                <button disabled={!canWrite || busy} onClick={() => report(m)}>
                  Report {m.handle} message
                </button>
              )}
            </li>
          ))}
      </ol>
      {props.nudgeSlot}
      {!props.actions && (
        <p className="cst-notice">
          Not connected. Waiting for the verified chat service.
        </p>
      )}
      <form
        className="cst-composer"
        onSubmit={(event) => {
          event.preventDefault();
          send();
        }}
      >
        <label htmlFor={`draft-${room.roomId}`}>
          Message your constellation
        </label>
        <textarea
          id={`draft-${room.roomId}`}
          value={draft}
          maxLength={500}
          disabled={!canWrite || busy}
          onChange={(event) => setDraft(event.target.value)}
          placeholder="A small hello is a good start."
        />
        <div className="cst-composer-footer">
          <small>
            {draft.length}/500 | No contact details or private answers
          </small>
          <button type="submit" disabled={!canWrite || busy || !draft.trim()}>
            Send
          </button>
        </div>
      </form>
      {busy && (
        <button
          onClick={() => {
            request.current.controller?.abort();
            request.current.seq += 1;
            setBusy(false);
          }}
        >
          Cancel pending action
        </button>
      )}
      {error && (
        <p className="cst-error" role="alert">
          {error}{" "}
          {retry && (
            <button disabled={busy || !canWrite} onClick={retry}>
              Retry action
            </button>
          )}
        </p>
      )}
      {supportAvailable && <SupportCard />}
    </section>
  );
}
