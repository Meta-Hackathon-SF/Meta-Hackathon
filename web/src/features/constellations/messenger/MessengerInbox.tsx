import { useState } from "react";
import { useSearchParams } from "react-router";
import { Users, X } from "lucide-react";
import Avatar from "../../../components/common/Avatar";
import { currentUser, people } from "../../../data/demo";
import { SUNDAY_THREAD_ID, addMuseMessage, sendInboxMessage, useInbox, type InboxThread } from "./inbox";
import { askMuse, type MuseKind } from "./museHelp";

const VIBE_KEY = "fb-space-messenger-vibe-closed";

function vibeClosed(): boolean {
  try {
    return sessionStorage.getItem(VIBE_KEY) === "1";
  } catch {
    return false;
  }
}

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
  return <Avatar person={person(thread.title)} online />;
}

function SharedVibe({ onClose }: { onClose: () => void }) {
  return (
    <aside className="vibe-card">
      <button type="button" className="vibe-close" aria-label="Close shared vibe" onClick={onClose}>
        <X size={16} />
      </button>
      <strong>Same vibe</strong>
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
  if (!selected) return null;
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
      <div className="conversation" role="region" aria-label={selected.title}>
        <header>
          <ThreadMark thread={selected} />
          <span>
            <strong>{selected.title}</strong>
            <small>
              {selected.kind === "group"
                ? `${selected.memberNames.join(", ")} · names visible`
                : "Demo conversation"}
            </small>
          </span>
        </header>
        <div className="conversation-body">
          {selected.kind === "direct" && (
            <>
              <Avatar person={person(selected.title)} size={56} />
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
              {message.linkHref && message.linkLabel && (
                <a className="muse-link" href={message.linkHref}>
                  {message.linkLabel}
                </a>
              )}
            </div>
          ))}
          {asking && <p className="muted">Muse is writing…</p>}
        </div>
        {selected.id === SUNDAY_THREAD_ID && (
          <div className="muse-actions">
            <span className="muse-hint">{draft.trim() ? "Sends this to @muse." : "Write a message first."}</span>
            {(
              [
                ["hangout", "Plan a hangout"],
                ["supplies", "Find supplies"],
                ["barter", "Ask a vendor"],
              ] as const
            ).map(([kind, label]) => (
              <button
                key={kind}
                type="button"
                disabled={asking !== null || !draft.trim()}
                onClick={() => {
                  const threadId = selected.id;
                  const note = draft.trim();
                  if (!note) return;
                  const spoken = /@muse\b/i.test(note) ? note : `${note} @muse`;
                  const context = [
                    ...selected.messages.map((message) => ({
                      sender: message.fromMuse ? "Muse" : message.senderName,
                      text: message.text,
                    })),
                    { sender: "Alex Morgan", text: spoken },
                  ];
                  sendInboxMessage(threadId, spoken);
                  setDraft("");
                  setAsking(kind);
                  void askMuse(kind, context).then((help) => {
                    addMuseMessage(threadId, help.text, help.source, help.link);
                    setAsking(null);
                  });
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
            if (!draft.trim()) return;
            sendInboxMessage(selected.id, draft);
            setDraft("");
          }}
        >
          <input
            aria-label="Message"
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            placeholder="Aa"
            maxLength={2000}
          />
          <button type="submit" aria-label="Send message" disabled={!draft.trim()}>
            Send
          </button>
        </form>
      </div>
    </section>
  );
}
