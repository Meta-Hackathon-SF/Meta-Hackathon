import { useState } from "react";
import { useSearchParams } from "react-router";
import { Users } from "lucide-react";
import Avatar from "../../../components/common/Avatar";
import { currentUser, people } from "../../../data/demo";
import { sendInboxMessage, useInbox, type InboxThread } from "./inbox";

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
