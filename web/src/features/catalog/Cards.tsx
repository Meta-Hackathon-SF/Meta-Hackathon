/* Compact catalog cards, used in Messenger (Muse replies), Space and the pages. */
import { Link } from "react-router";
import { CalendarDays, Check, MapPin, Sparkles } from "lucide-react";
import { draftWhen, eventImage, findItem, itemImage, venueName, type CatalogEvent, type EventDraft } from "./catalog";
import { goingCount, isRegistered, toggleRegistration, useCatalogState } from "./store";
import "./catalog.css";

export function RegisterButton({ event, compact }: { event: CatalogEvent; compact?: boolean }) {
  const s = useCatalogState();
  const on = isRegistered(event.eventId, s);
  return (
    <button
      type="button"
      className={`${on ? "button-secondary" : "button-primary"} cat-register${compact ? " is-compact" : ""}`}
      aria-pressed={on}
      aria-label={on ? `Registered for ${event.title}. Cancel registration` : `Register for ${event.title}`}
      onClick={() => toggleRegistration(event.eventId)}
    >
      {on ? <Check size={16} aria-hidden="true" /> : <CalendarDays size={16} aria-hidden="true" />}
      {on ? "Going" : "Register"}
    </button>
  );
}

export function ItemCard({ itemId }: { itemId: string }) {
  const item = findItem(itemId);
  if (!item) return null;
  return (
    <Link className="cat-card" to={`/marketplace/${item.itemId}`} data-testid={`cat-item-${item.itemId}`}>
      <img src={itemImage(item)} alt="" />
      <span className="cat-card-body">
        <b>{item.price}</b>
        <span className="cat-card-title">{item.title}</span>
        <small>
          {item.place} · Demo listing
        </small>
      </span>
    </Link>
  );
}

export function EventCard({ event }: { event: CatalogEvent }) {
  const s = useCatalogState();
  return (
    <div className="cat-card is-event" data-testid={`cat-event-${event.eventId}`}>
      <Link to={`/events/${event.eventId}`} className="cat-card-link">
        <img src={eventImage(event)} alt="" />
        <span className="cat-card-body">
          <small className="cat-when">{event.when}</small>
          <span className="cat-card-title">{event.title}</span>
          <small>
            {venueName(event.placeId)} · {goingCount(event, s)} going
          </small>
        </span>
      </Link>
      <RegisterButton event={event} compact />
    </div>
  );
}

export function DraftCard({
  draft,
  createdId,
  onCreate,
}: {
  draft: EventDraft;
  createdId?: string;
  onCreate: () => void;
}) {
  return (
    <div className="cat-card is-draft" data-testid="cat-draft">
      <span className="cat-draft-head">
        <Sparkles size={14} aria-hidden="true" /> Event draft from Muse
      </span>
      <span className="cat-card-title">{draft.title}</span>
      <small>
        <MapPin size={12} aria-hidden="true" /> {venueName(draft.placeId)} · {draftWhen(draft)}
      </small>
      {draft.description && <small className="cat-draft-desc">{draft.description}</small>}
      {createdId ? (
        <Link className="button-secondary cat-register is-compact" to={`/events/${createdId}`}>
          <Check size={16} aria-hidden="true" /> Created · View event
        </Link>
      ) : (
        <button type="button" className="button-primary cat-register is-compact" onClick={onCreate}>
          Create event
        </button>
      )}
      <small className="cat-fine">Nothing is posted until you tap Create. Demo event, venue from the approved list.</small>
    </div>
  );
}
