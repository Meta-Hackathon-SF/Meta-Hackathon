import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router";
import { Users, X } from "lucide-react";
import Avatar from "../../../components/common/Avatar";
import { currentUser, people } from "../../../data/demo";
import { SUNDAY_THREAD_ID, addMuseMessage, sendInboxMessage, useInbox, type InboxThread } from "./inbox";
import { LiveGroupThread } from "./LiveGroupThread";
import { MessageCards } from "./MessageCards";
import { anonymize, askMuse, inferKind, type MuseKind } from "./museHelp";

const SUGGESTIONS: [MuseKind, string, string][] = [
  ["hangout", "Find an event", "@muse what's happening this week that we'd like?"],
  ["create", "Create an event", "@muse create a study session on Thursday at 7pm"],
  ["supplies", "Find supplies", "@muse what should we bring?"],
];
/** A thread opened from a mutual reveal offers the two catalog actions only. */
const REVEAL_KINDS: MuseKind[] = ["hangout", "create"];

import "../daily/space/space.css";

const VIBE_KEY = "fb-space-messenger-vibe-closed";

function vibeClosed(): boolean {
  try {
    return sessionStorage.getItem(VIBE_KEY) === "1";
  } catch {
    return false;
  }
}

/** Threads opened from a real mutual reveal: the person is not one of the demo profiles. */
const isReveal = (thread: InboxThread) => thread.id.startsWith("reveal-");

function person(name: string) {
  return people.find((entry) => entry.name === name) ?? currentUser;
}

function ThreadMark({ thread }: { thread: InboxThread }) {
  if (thread.kind === "group") {
    return (
      <span className="avatar group-chip" aria-hidden="true">
        <Users size={18} />
      </span>
    );
  }
  if (isReveal(thread)) {
    return (
      <span className="avatar group-chip" aria-hidden="true">
        {thread.title.slice(0, 1).toUpperCase()}
      </span>
    );
  }
  return <Avatar person={person(thread.title)} online />;
}

function SharedVibe({ onClose }: { onClose: () => void }) {
  return (
    <aside className="vibe-card">
      <button type="button" className="vibe-close" aria-label="Close shared vibe" onClick={onClose}>
        <X size={16} />
      </button>
      <strong>
        Same vibe <span className="spc-preview">Preview</span>
      </strong>
      <p>
        You all thought you were the only one feeling it, and Tuesday&apos;s question is what brought it out. That&apos;s an easy place to start.
      </p>
    </aside>
  );
}

export default function MessengerInbox() {
  const threads = useInbox();
  const [params, setParams] = useSearchParams();
  const requested = params.get("chat");
  const selected = threads.find((thread) => thread.id === requested) ?? threads[0];
  const [draft, setDraft] = useState("");
  const [asking, setAsking] = useState<MuseKind | null>(null);
  const [vibeOpen, setVibeOpen] = useState(() => !vibeClosed());
  const input = useRef<HTMLInputElement | null>(null);
  const end = useRef<HTMLDivElement | null>(null);
  const count = selected?.messages.length ?? 0;
  useEffect(() => {
    end.current?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [count, asking, selected?.id]);
  if (!selected) return null;
  const isSunday = selected.id === SUNDAY_THREAD_ID;
  const fromReveal = isReveal(selected);
  const museOn = isSunday || fromReveal;
  const suggestions = fromReveal ? SUGGESTIONS.filter(([kind]) => REVEAL_KINDS.includes(kind)) : SUGGESTIONS;

  /** Sends the draft. Where Muse is on, a message that mentions @muse also asks Muse. */
  const submit = (forced?: MuseKind) => {
    const note = draft.trim();
    if (!note || asking) return;
    const threadId = selected.id;
    const wantsMuse = museOn && (forced !== undefined || /@muse\b/i.test(note));
    const spoken = wantsMuse && !/@muse\b/i.test(note) ? `${note} @muse` : note;
    sendInboxMessage(threadId, spoken);
    setDraft("");
    if (!wantsMuse) return;
    const kind = forced ?? inferKind(note);
    const context = anonymize([
      ...selected.messages.map((m) => ({ sender: m.senderName, text: m.text, mine: m.mine, fromMuse: Boolean(m.fromMuse) })),
      { sender: "You", text: spoken, mine: true, fromMuse: false },
    ]);
    setAsking(kind);
    void askMuse(kind, context).then((help) => {
      addMuseMessage(threadId, help);
      setAsking(null);
    });
  };
  const showVibe = vibeOpen && selected.id === SUNDAY_THREAD_ID;

  return (
    <section className="card messenger-page">
      <div className="conversation-list">
        {threads.map((thread) => (
          <button
            key={thread.id}
            className={selected.id === thread.id ? "selected" : ""}
            onClick={() => setParams({ chat: thread.id })}
            aria-label={`Chat with ${thread.title}`}
            aria-current={selected.id === thread.id ? "true" : undefined}
          >
            <ThreadMark thread={thread} />
            <span>{thread.title}</span>
          </button>
        ))}
      </div>
      {selected.live ? (
        <LiveGroupThread key={selected.live.roomId} thread={selected} suggestions={SUGGESTIONS} />
      ) : (
      <div className="conversation" role="region" aria-label={selected.title}>
        <header>
          <ThreadMark thread={selected} />
          <span>
            <strong>{selected.title}</strong>
            <small>
              {selected.kind === "group"
                ? `${selected.memberNames.join(", ")} · names visible · Preview`
                : isReveal(selected)
                  ? `${selected.synthetic ? "Synthetic player · " : ""}Simulated Facebook`
                  : "Demo conversation"}
            </small>
          </span>
        </header>
        <div className="conversation-body">
          {selected.kind === "direct" && (
            <>
              {!isReveal(selected) && <Avatar person={person(selected.title)} size={56} />}
              <h2>{selected.title}</h2>
              <p className="muted">You're connected in the hackathon community.</p>
            </>
          )}
          {showVibe && (
            <SharedVibe
              onClose={() => {
                setVibeOpen(false);
                try {
                  sessionStorage.setItem(VIBE_KEY, "1");
                } catch {
                  /* The note stays closed for this view if storage is blocked. */
                }
              }}
            />
          )}
          {selected.messages.map((message) => (
            <div key={message.id} className="thread-line">
              {!message.mine && (
                <small className="thread-sender">
                  {message.fromMuse ? (message.source === "catalog" ? "Muse · catalog" : "Muse") : message.senderName}
                </small>
              )}
              <p className={message.mine ? "sent-message" : message.fromMuse ? "muse-message" : "received-message"}>
                {message.text}
              </p>
              <MessageCards threadId={selected.id} message={message} />
            </div>
          ))}
          {asking && <p className="muted">Muse is writing…</p>}
          <div ref={end} />
        </div>
        {museOn && (
          <div className="muse-actions" role="group" aria-label="Ask Muse">
            <span className="muse-hint">Mention @muse to get a suggestion, or tap one:</span>
            {suggestions.map(([kind, label, text]) => (
              <button
                key={kind}
                type="button"
                disabled={asking !== null}
                onClick={() => {
                  setDraft(text);
                  input.current?.focus();
                }}
              >
                {label}
              </button>
            ))}
          </div>
        )}
        <form
          onSubmit={(event) => {
            event.preventDefault();
            submit();
          }}
        >
          <input
            ref={input}
            aria-label="Message"
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            placeholder={museOn ? "Aa · mention @muse for ideas" : "Aa"}
            maxLength={2000}
          />
          <button type="submit" aria-label="Send message" disabled={!draft.trim() || asking !== null}>
            Send
          </button>
        </form>
      </div>
      )}
    </section>
  );
}
