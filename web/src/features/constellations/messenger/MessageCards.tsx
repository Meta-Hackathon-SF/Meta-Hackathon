/* Catalog cards and Muse event drafts attached to a Messenger line. */
import { currentUser } from "../../../data/demo";
import { DraftCard, EventCard, ItemCard } from "../../catalog/Cards";
import { createEvent, findEvent, useCatalogState } from "../../catalog/store";
import { markDraftCreated, type InboxMessage } from "./inbox";

export function MessageCards({ threadId, message }: { threadId: string; message: InboxMessage }) {
  const catalog = useCatalogState();
  if (!message.itemIds?.length && !message.eventIds?.length && !message.draft) return null;
  return (
    <div className={`cat-cards${message.mine ? " is-mine" : ""}`}>
      {message.itemIds?.map((id) => <ItemCard key={id} itemId={id} />)}
      {message.eventIds?.map((id) => {
        const event = findEvent(id, catalog);
        return event ? <EventCard key={id} event={event} /> : null;
      })}
      {message.draft && (
        <DraftCard
          draft={message.draft}
          createdId={message.createdEventId}
          onCreate={() => {
            const event = createEvent(message.draft!, currentUser.name);
            markDraftCreated(threadId, message.id, event.eventId, event.title);
          }}
        />
      )}
    </div>
  );
}
