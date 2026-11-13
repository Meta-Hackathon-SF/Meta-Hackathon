/* Marketplace and Events pages backed by the demo catalog. */
import { Link, useParams } from "react-router";
import { ArrowLeft, CalendarDays, MapPin, MessageCircle, Sparkles, Tag, Users } from "lucide-react";
import PageFrame from "../../layouts/PageFrame";
import { useApp } from "../../state/context";
import { eventImage, findItem, itemImage, ITEMS, venueName } from "./catalog";
import { RegisterButton } from "./Cards";
import { allEvents, findEvent, goingCount, isRegistered, useCatalogState } from "./store";
import "./catalog.css";

export function MarketplacePage() {
  return (
    <PageFrame title="Marketplace" description="Discover a few finds in your community.">
      <div className="section-heading">
        <h2>Today's picks</h2>
        <span className="location-label">
          <MapPin size={16} />
          Santa Cruz · 40 mi
        </span>
      </div>
      <div className="marketplace-grid">
        {ITEMS.map((item) => (
          <Link className="marketplace-item" key={item.itemId} to={`/marketplace/${item.itemId}`}>
            <img src={itemImage(item)} alt={item.title} />
            <strong>{item.price}</strong>
            <span>{item.title}</span>
            <small>{item.place}</small>
          </Link>
        ))}
      </div>
      <p className="muted demo-page-note">Demonstration listings only. No purchases or payments.</p>
    </PageFrame>
  );
}

export function MarketplaceItemPage() {
  const { itemId = "" } = useParams();
  const { notify } = useApp();
  const item = findItem(itemId);
  if (!item)
    return (
      <PageFrame title="Listing not found">
        <Link className="button-primary" to="/marketplace">
          Back to Marketplace
        </Link>
      </PageFrame>
    );
  return (
    <PageFrame title="Marketplace">
      <Link className="cat-back" to="/marketplace">
        <ArrowLeft size={16} /> All listings
      </Link>
      <article className="card cat-detail" data-testid="cat-item-detail">
        <img src={itemImage(item)} alt={item.title} />
        <div className="cat-detail-body">
          <h2>{item.title}</h2>
          <p className="cat-price">{item.price}</p>
          <p className="muted">
            <MapPin size={14} aria-hidden="true" /> {item.place} · {item.condition} · {item.category}
          </p>
          <p>{item.description}</p>
          <p className="muted">
            <Tag size={14} aria-hidden="true" /> Listed by {item.seller}
          </p>
          <div className="cat-actions">
            <button
              type="button"
              className="button-primary"
              onClick={() => notify(`Messaging sellers is not part of this demo. ${item.title} is a demo listing.`)}
            >
              <MessageCircle size={18} /> Message seller
            </button>
          </div>
          <p className="cat-fine">Demo listing. Nothing is sold, bought or paid for.</p>
        </div>
      </article>
    </PageFrame>
  );
}

export function EventsPage() {
  const s = useCatalogState();
  const events = allEvents(s);
  const mine = events.filter((e) => isRegistered(e.eventId, s));
  return (
    <PageFrame title="Events" description="Make plans. Make connections.">
      {mine.length > 0 && (
        <section className="card cat-going" aria-labelledby="cat-going-title">
          <h2 id="cat-going-title">You're going</h2>
          <ul>
            {mine.map((e) => (
              <li key={e.eventId}>
                <Link to={`/events/${e.eventId}`}>{e.title}</Link>
                <small className="muted">
                  {e.when} · {venueName(e.placeId)}
                </small>
              </li>
            ))}
          </ul>
        </section>
      )}
      <div className="cat-event-grid">
        {events.map((e) => (
          <article className="card cat-event" key={e.eventId} data-testid={`cat-event-row-${e.eventId}`}>
            <Link to={`/events/${e.eventId}`} className="cat-event-link">
              <img src={eventImage(e)} alt="" />
              <span className="cat-event-when">{e.when}</span>
              <h2>{e.title}</h2>
              <span className="muted">
                {venueName(e.placeId)} · {goingCount(e, s)} going
              </span>
              {e.createdBy && (
                <span className="cat-muse-tag">
                  <Sparkles size={12} aria-hidden="true" /> Created with Muse
                </span>
              )}
            </Link>
            <RegisterButton event={e} />
          </article>
        ))}
      </div>
      <p className="muted demo-page-note">Fictional demo events. Registering only saves in this browser.</p>
    </PageFrame>
  );
}

export function EventPage() {
  const { eventId = "" } = useParams();
  const s = useCatalogState();
  const event = findEvent(eventId, s);
  if (!event)
    return (
      <PageFrame title="Event not found">
        <Link className="button-primary" to="/events">
          Back to Events
        </Link>
      </PageFrame>
    );
  const going = goingCount(event, s);
  return (
    <PageFrame title="Events">
      <Link className="cat-back" to="/events">
        <ArrowLeft size={16} /> All events
      </Link>
      <article className="card cat-detail is-event" data-testid="cat-event-detail">
        <img src={eventImage(event)} alt="" />
        <div className="cat-detail-body">
          <p className="event-eyebrow">{event.when}</p>
          <h2>{event.title}</h2>
          <p className="muted">
            <MapPin size={14} aria-hidden="true" /> {venueName(event.placeId)} · Hosted by {event.host}
          </p>
          {event.createdBy && (
            <p className="cat-muse-tag">
              <Sparkles size={12} aria-hidden="true" /> Created with Muse in Messenger
            </p>
          )}
          <p>{event.description}</p>
          <p className="muted">
            <Users size={14} aria-hidden="true" /> {going} going · {Math.max(0, event.capacity - going)} spots left
          </p>
          <div className="cat-actions">
            <RegisterButton event={event} />
            <Link className="button-secondary" to="/events">
              <CalendarDays size={18} /> More events
            </Link>
          </div>
          <p className="cat-fine">Fictional demo event. Registering only saves in this browser.</p>
        </div>
      </article>
    </PageFrame>
  );
}
