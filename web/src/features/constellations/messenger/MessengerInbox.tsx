import { useState } from "react";
import { useSearchParams } from "react-router";
import { Users } from "lucide-react";
import Avatar from "../../../components/common/Avatar";
import { people } from "../../../data/demo";
import { sendInboxMessage, useInbox, type InboxThread } from "./inbox";

function person(name: string) {
  return people.find((entry) => entry.name === name);
}

function ThreadMark({ thread, size }: { thread: InboxThread; size?: number }) {
  const known = thread.kind === "direct" ? person(thread.title) : undefined;
  if (known) return <Avatar person={known} online size={size} />;
  // No stock photo for a group or for someone who is not a shell demo person.
  return (
    <span className="avatar group-chip" aria-hidden="true">
      {thread.kind === "group" ? <Users size={18} /> : thread.title.slice(0, 1).toUpperCase()}
    </span>
  );
}

export default function MessengerInbox() {
  const threads = useInbox();
  const [params, setParams] = useSearchParams();
  const requested = params.get("chat");
  const selected = threads.find((thread) => thread.id === requested) ?? threads[0];
  const [draft, setDraft] = useState("");
  if (!selected) return null;

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
                : selected.id.startsWith("reveal-") ? "Simulated Facebook" : "Demo conversation"}
            </small>
          </span>
        </header>
        <div className="conversation-body">
          {selected.kind === "direct" && (
            <>
              <ThreadMark thread={selected} size={56} />
              <h2>{selected.title}</h2>
              <p className="muted">
                {selected.id.startsWith("reveal-")
                  ? "Simulated Facebook. You both chose to reveal in Space. Messages here stay in this browser."
                  : "You're connected in the hackathon community."}
              </p>
            </>
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
        </div>
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
