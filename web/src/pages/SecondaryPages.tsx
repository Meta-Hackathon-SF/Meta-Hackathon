import { useState } from "react";
import { Link } from "react-router";
import {
  Bookmark,
  CalendarDays,
  Camera,
  Check,
  ChevronRight,
  Globe,
  MapPin,
  Pencil,
  Play,
  Plus,
  Send,
  Users,
} from "lucide-react";
import PageFrame from "../layouts/PageFrame";
import Avatar from "../components/common/Avatar";
import PostCard from "../components/feed/PostCard";
import Composer from "../components/feed/Composer";
import { currentUser, notifications, people, photo } from "../data/demo";
import { useApp } from "../state/context";

export function FriendsPage() {
  const [responses, setResponses] = useState<Record<string, string>>({});
  return (
    <PageFrame title="Friends">
      <div className="section-heading">
        <h2>Friend requests</h2>
        <span className="muted">2 requests</span>
      </div>
      <div className="people-grid">
        {people.slice(0, 2).map((person, index) => (
          <article className="card person-card" key={person.name}>
            <img
              className="person-photo"
              src={person.avatar}
              alt={person.name}
            />
            <div>
              <h3>{person.name}</h3>
              <p className="muted">{index ? "8" : "12"} mutual friends</p>
              {responses[person.name] ? (
                <p className="person-response">
                  <Check size={17} />
                  {responses[person.name]}
                </p>
              ) : (
                <>
                  <button
                    className="button-primary"
                    onClick={() =>
                      setResponses({
                        ...responses,
                        [person.name]: "You are now friends",
                      })
                    }
                  >
                    Confirm
                  </button>
                  <button
                    className="button-secondary"
                    onClick={() =>
                      setResponses({
                        ...responses,
                        [person.name]: "Request removed",
                      })
                    }
                  >
                    Delete
                  </button>
                </>
              )}
            </div>
          </article>
        ))}
      </div>
      <div className="section-heading">
        <h2>People you may know</h2>
      </div>
      <div className="people-grid">
        {people.slice(2, 5).map((person) => (
          <article className="card person-card" key={person.name}>
            <img
              className="person-photo"
              src={person.avatar}
              alt={person.name}
            />
            <div>
              <h3>{person.name}</h3>
              <p className="muted">From your campus community</p>
              <button
                className="button-soft"
                disabled={!!responses[person.name]}
                onClick={() =>
                  setResponses({ ...responses, [person.name]: "Request sent" })
                }
              >
                {responses[person.name] || "Add friend"}
              </button>
            </div>
          </article>
        ))}
      </div>
    </PageFrame>
  );
}

export function GroupsPage() {
  const [joined, setJoined] = useState<string[]>([]);
  return (
    <PageFrame
      title="Groups"
      description="Discover people who share your interests."
    >
      <h2 className="section-heading">Suggested for you</h2>
      <div className="discovery-grid">
        {[
          {
            name: "Hackathon Builders Community",
            image: "team",
            members: "1.2K members · 8 posts a day",
          },
          {
            name: "Meta AI Explorers",
            image: "workspace",
            members: "845 members · 5 posts a day",
          },
          {
            name: "XR Student Collective",
            image: "headset",
            members: "328 members · 3 posts a day",
          },
        ].map((group) => (
          <article className="card discovery-card" key={group.name}>
            <img src={photo(group.image)} alt={group.name} />
            <div>
              <h3>{group.name}</h3>
              <p className="muted">{group.members}</p>
              <button
                className={
                  joined.includes(group.name)
                    ? "button-secondary"
                    : "button-soft"
                }
                onClick={() =>
                  setJoined((previous) =>
                    previous.includes(group.name)
                      ? previous.filter((name) => name !== group.name)
                      : [...previous, group.name],
                  )
                }
              >
                {joined.includes(group.name) ? (
                  <>
                    <Check size={17} />
                    Joined
                  </>
                ) : (
                  "Join group"
                )}
              </button>
            </div>
          </article>
        ))}
      </div>
    </PageFrame>
  );
}

export function MarketplacePage() {
  const { notify } = useApp();
  return (
    <PageFrame
      title="Marketplace"
      description="Discover a few finds in your community."
    >
      <div className="section-heading">
        <h2>Today's picks</h2>
        <span className="location-label">
          <MapPin size={16} />
          Santa Cruz · 40 mi
        </span>
      </div>
      <div className="marketplace-grid">
        {[
          {
            image: "code",
            price: "$250",
            title: "Laptop and desk setup",
            place: "Santa Cruz, CA",
          },
          {
            image: "headset",
            price: "$120",
            title: "VR headset · like new",
            place: "San Jose, CA",
          },
          {
            image: "coffee",
            price: "$20",
            title: "Coffee set for your next study session",
            place: "Santa Cruz, CA",
          },
          {
            image: "library",
            price: "Free",
            title: "Textbook exchange",
            place: "Campus pickup",
          },
        ].map((item) => (
          <button
            className="marketplace-item"
            key={item.title}
            onClick={() =>
              notify(
                `${item.title} · Demo listing. Buying and messaging sellers will be available in a future version.`,
              )
            }
          >
            <img src={photo(item.image)} alt={item.title} />
            <strong>{item.price}</strong>
            <span>{item.title}</span>
            <small>{item.place}</small>
          </button>
        ))}
      </div>
      <p className="muted demo-page-note">
        Demonstration listings only. No purchases or payments.
      </p>
    </PageFrame>
  );
}

export function WatchPage() {
  const { notify } = useApp();
  return (
    <PageFrame
      title="Reels"
      description="A little inspiration from your community."
    >
      <section className="reel-preview">
        <img src={photo("headset")} alt="Exploring virtual reality" />
        <div className="reel-caption">
          <strong>XR Student Collective</strong>
          <p>A whole new way to connect. 💙</p>
          <span>Demo preview</span>
        </div>
        <button
          className="reel-play"
          aria-label="Play demo reel"
          onClick={() =>
            notify(
              "This is a static reel preview. Video playback is a placeholder for the next build.",
            )
          }
        >
          <Play size={34} fill="white" />
        </button>
      </section>
    </PageFrame>
  );
}

export function EventsPage() {
  const [going, setGoing] = useState(false);
  return (
    <PageFrame title="Events" description="Make plans. Make connections.">
      <section className="card event-card">
        <img src={photo("team")} alt="Community members building together" />
        <div>
          <p className="event-eyebrow">SAT, NOV 14 · 6 PM</p>
          <h2>Build together: community demo night</h2>
          <p className="muted">Student Innovation Lab · Fictional demo event</p>
          <p>
            Bring your prototype, meet other student builders, and share what
            you've learned.
          </p>
          <button
            className={going ? "button-secondary" : "button-primary"}
            onClick={() => setGoing(!going)}
          >
            {going ? (
              <>
                <Check size={18} />
                Going
              </>
            ) : (
              <>
                <CalendarDays size={18} />
                Interested
              </>
            )}
          </button>
        </div>
      </section>
    </PageFrame>
  );
}

export function SavedPage() {
  const { posts } = useApp();
  const saved = posts.filter((post) => post.saved && !post.hidden);
  return (
    <PageFrame
      title="Saved"
      description="A little collection of things to come back to."
    >
      <div className="saved-feed">
        {saved.length ? (
          saved.map((post) => <PostCard post={post} key={post.id} />)
        ) : (
          <div className="card empty-state">
            <Bookmark size={40} />
            <h2>Save something you love</h2>
            <p>
              Open a post's three-dot menu and choose Save post. You'll find it
              here.
            </p>
            <Link to="/" className="button-primary">
              Explore your Feed
            </Link>
          </div>
        )}
      </div>
    </PageFrame>
  );
}

export function MemoriesPage() {
  return (
    <PageFrame
      title="Memories"
      description="A look back at the moments that brought you together."
    >
      <section className="card memory-card">
        <img src={photo("campus")} alt="A sunny afternoon on campus" />
        <div>
          <h2>Here's to the first hello</h2>
          <p>New campus, new friends, and so many things still to build.</p>
          <p className="muted">A sample memory from your demo community.</p>
          <Link to="/" className="button-soft">
            See what's happening today
          </Link>
        </div>
      </section>
    </PageFrame>
  );
}

export function ProfilePage() {
  const { posts, setComposerOpen, notify } = useApp();
  const myPosts = posts.filter(
    (post) => post.author.name === currentUser.name && !post.hidden,
  );
  return (
    <PageFrame title="Your profile">
      <section className="card profile-card">
        <div className="profile-cover">
          <img src={photo("campus")} alt="Campus cover photo" />
          <button
            aria-label="Edit cover photo"
            className="icon-button"
            onClick={() =>
              notify("Cover photo editing is coming in a future version.")
            }
          >
            <Camera size={20} />
          </button>
        </div>
        <div className="profile-identity">
          <Avatar person={currentUser} size={112} />
          <div>
            <h2>{currentUser.name}</h2>
            <p className="muted">Student builder · Santa Cruz, California</p>
          </div>
        </div>
        <div className="profile-buttons">
          <button
            className="button-primary"
            onClick={() => setComposerOpen(true)}
          >
            <Plus size={18} />
            Add to story
          </button>
          <button
            className="button-secondary"
            onClick={() =>
              notify(
                "You are viewing the local demo profile. Profile editing is coming later.",
              )
            }
          >
            <Pencil size={17} />
            Edit profile
          </button>
        </div>
        <div className="profile-tabs">
          <strong>Posts</strong>
          <Link to="/friends">Friends</Link>
          <button
            onClick={() =>
              notify("Photo albums are a placeholder in this prototype.")
            }
          >
            Photos
          </button>
        </div>
      </section>
      <div className="profile-columns">
        <section className="card profile-intro">
          <h2>Intro</h2>
          <p>Building things that bring people closer together. 💙</p>
          <p>
            <MapPin size={18} />
            Lives in <strong>Santa Cruz, California</strong>
          </p>
          <p>
            <Users size={18} />
            Member of Hackathon Builders
          </p>
          <span className="muted">Fictional demonstration profile</span>
        </section>
        <div className="profile-feed">
          <Composer />
          {myPosts.map((post) => (
            <PostCard key={post.id} post={post} />
          ))}
        </div>
      </div>
    </PageFrame>
  );
}

export function NotificationsPage() {
  const { readNotifications, markNotificationsRead } = useApp();
  return (
    <PageFrame title="Notifications">
      <div className="card notifications-page">
        <div className="section-heading">
          <h2>New</h2>
          <button className="text-button" onClick={markNotificationsRead}>
            Mark all as read
          </button>
        </div>
        {notifications.map((item) => (
          <Link
            key={item.id}
            className={`notification-row ${!readNotifications && item.unread ? "unread" : ""}`}
            to={item.to}
          >
            <Avatar person={item.person} size={60} />
            <span>
              {item.text}
              <small>{item.time} ago</small>
            </span>
            {!readNotifications && item.unread && <i className="unread-dot" />}
            <ChevronRight size={20} />
          </Link>
        ))}
      </div>
    </PageFrame>
  );
}

export function MessagesPage() {
  const [selected, setSelected] = useState(people[0]);
  const [draft, setDraft] = useState("");
  const [messages, setMessages] = useState<Record<string, string[]>>({});
  return (
    <PageFrame
      title="Messenger"
      description="A local chat preview. Messages stay in this page."
    >
      <section className="card messenger-page">
        <div className="conversation-list">
          {people.slice(0, 4).map((person) => (
            <button
              key={person.name}
              className={selected.name === person.name ? "selected" : ""}
              onClick={() => setSelected(person)}
              aria-label={`Chat with ${person.name}`}
            >
              <Avatar person={person} online />
              <span>{person.name}</span>
            </button>
          ))}
        </div>
        <div className="conversation">
          <header>
            <Avatar person={selected} size={36} online />
            <span>
              <strong>{selected.name}</strong>
              <small>Demo conversation</small>
            </span>
          </header>
          <div className="conversation-body">
            <Avatar person={selected} size={56} />
            <h2>{selected.name}</h2>
            <p className="muted">
              You're connected in the hackathon community.
            </p>
            <p className="received-message">
              Hey! See you at the next build session? 👋
            </p>
            {messages[selected.name]?.map((text, index) => (
              <p className="sent-message" key={index}>
                {text}
              </p>
            ))}
          </div>
          <form
            onSubmit={(event) => {
              event.preventDefault();
              if (!draft.trim()) return;
              setMessages((previous) => ({
                ...previous,
                [selected.name]: [
                  ...(previous[selected.name] || []),
                  draft.trim(),
                ],
              }));
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
            <button
              type="submit"
              aria-label="Send message"
              disabled={!draft.trim()}
            >
              <Send size={21} />
            </button>
          </form>
        </div>
      </section>
    </PageFrame>
  );
}

export function NotFoundPage() {
  return (
    <PageFrame title="This page isn't available">
      <section className="card empty-state">
        <Globe size={40} />
        <h2>Let's get you back to your community.</h2>
        <Link to="/" className="button-primary">
          Go to Feed
        </Link>
      </section>
    </PageFrame>
  );
}
