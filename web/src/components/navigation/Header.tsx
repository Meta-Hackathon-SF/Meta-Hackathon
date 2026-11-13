import { useEffect, useRef, useState } from "react";
import { Link, NavLink, useLocation, useNavigate } from "react-router";
import {
  Bell,
  ChevronDown,
  CircleHelp,
  Menu,
  Plus,
  Search,
  Settings,
  X,
} from "lucide-react";
import Avatar from "../common/Avatar";
import IconButton from "../common/IconButton";
import { currentUser, notifications, people } from "../../data/demo";
import { useApp } from "../../state/context";
import { primaryNavigation, sidebarNavigation } from "./navigation";
import NavigationIcon from "./NavigationIcon";

type Panel =
  "menu" | "messages" | "notifications" | "profile" | "search" | null;

export function MessengerIcon() {
  return (
    <svg
      viewBox="0 0 28 28"
      width="23"
      height="23"
      fill="currentColor"
      aria-hidden="true"
    >
      <path d="M14 2C7.1 2 2 6.9 2 13.4c0 3.7 1.6 6.8 4.3 8.8V26l4.1-2.3c1.1.3 2.3.5 3.6.5 6.9 0 12-4.9 12-11.4S20.9 2 14 2Z" />
      <path d="m6.9 17 6-6.4 3.4 2.6 4.8-2.6-5.9 6.5-3.4-2.7Z" fill="white" />
    </svg>
  );
}

export default function Header() {
  const [panel, setPanel] = useState<Panel>(null);
  const [query, setQuery] = useState("");
  const ref = useRef<HTMLElement>(null);
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const { setComposerOpen, readNotifications, markNotificationsRead, notify } =
    useApp();
  const title =
    pathname === "/watch"
      ? "Reels"
      : pathname
          .slice(1)
          .split("/")[0]
          .replace(/^\w/, (char) => char.toUpperCase());

  useEffect(() => {
    function dismiss(event: PointerEvent) {
      if (!ref.current?.contains(event.target as Node)) setPanel(null);
    }
    function escape(event: KeyboardEvent) {
      if (event.key === "Escape") setPanel(null);
    }
    document.addEventListener("pointerdown", dismiss);
    document.addEventListener("keydown", escape);
    return () => {
      document.removeEventListener("pointerdown", dismiss);
      document.removeEventListener("keydown", escape);
    };
  }, []);

  function toggle(next: Panel) {
    setPanel((previous) => (previous === next ? null : next));
  }
  function close() {
    setPanel(null);
  }
  function search(event: React.SubmitEvent<HTMLFormElement>) {
    event.preventDefault();
    navigate(query.trim() ? `/?q=${encodeURIComponent(query.trim())}` : "/");
    close();
  }

  return (
    <header className="topbar" ref={ref}>
      <div className="header-brand">
        <IconButton
          label="Open menu"
          className="mobile-menu"
          aria-expanded={panel === "menu"}
          onClick={() => toggle("menu")}
        >
          <Menu />
        </IconButton>
        <Link
          to="/"
          className="facebook-logo"
          aria-label="Facebook home"
          onClick={close}
        >
          <svg viewBox="0 0 40 40" aria-hidden="true">
            <circle cx="20" cy="20" r="20" fill="#0866ff" />
            <path
              fill="white"
              d="M22.9 40V24.5h5.2l.8-6h-6v-3.8c0-1.7.5-2.9 3-2.9h3.2V6.4c-.6-.1-2.5-.3-4.7-.3-4.7 0-7.9 2.9-7.9 8.1v4.3h-5.3v6h5.3V40Z"
            />
          </svg>
        </Link>
        {pathname === "/" ? (
          <Link to="/" className="facebook-wordmark" onClick={close}>
            facebook
          </Link>
        ) : (
          <span className="mobile-page-title">{title}</span>
        )}
        <form className="header-search" role="search" onSubmit={search}>
          <Search size={20} aria-hidden="true" />
          <input
            aria-label="Search Facebook"
            placeholder="Search Facebook"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
        </form>
      </div>
      <nav className="desktop-tabs" aria-label="Main navigation">
        {primaryNavigation.map(({ to, label, icon }) => (
          <NavLink
            key={to}
            to={to}
            end
            title={label}
            aria-label={label}
            onClick={close}
          >
            {({ isActive }) => (
              <NavigationIcon icon={icon} label={label} active={isActive} />
            )}
          </NavLink>
        ))}
      </nav>
      <div className="header-controls">
        <IconButton
          label="Create a post"
          className="mobile-create"
          onClick={() => {
            close();
            setComposerOpen(true);
          }}
        >
          <Plus />
        </IconButton>
        <IconButton
          label="Search"
          className="mobile-search"
          aria-expanded={panel === "search"}
          onClick={() => toggle("search")}
        >
          <Search />
        </IconButton>
        <IconButton
          label="Menu"
          className="desktop-control"
          aria-expanded={panel === "menu"}
          onClick={() => toggle("menu")}
        >
          <svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true">
            {Array.from({ length: 9 }, (_, index) => (
              <rect
                key={index}
                x={2 + (index % 3) * 7}
                y={2 + Math.floor(index / 3) * 7}
                width="5"
                height="5"
                rx="1"
                fill="currentColor"
              />
            ))}
          </svg>
        </IconButton>
        <IconButton
          label="Messenger"
          aria-expanded={panel === "messages"}
          onClick={() => toggle("messages")}
        >
          <MessengerIcon />
          <span className="notification-badge mobile-message-badge">1</span>
        </IconButton>
        <IconButton
          label="Notifications"
          className="desktop-control"
          aria-expanded={panel === "notifications"}
          onClick={() => toggle("notifications")}
        >
          <Bell size={23} fill="currentColor" />
          {!readNotifications && <span className="notification-badge">3</span>}
        </IconButton>
        <button
          className="profile-control desktop-control"
          aria-label="Account"
          aria-expanded={panel === "profile"}
          onClick={() => toggle("profile")}
        >
          <Avatar person={currentUser} />
          <span className="profile-chevron">
            <ChevronDown size={13} />
          </span>
        </button>
      </div>
      {panel && (
        <section
          className={`header-panel panel-${panel}`}
          aria-label={
            panel === "profile"
              ? "Account menu"
              : panel === "menu"
                ? "Menu"
                : panel === "messages"
                  ? "Messenger"
                  : panel === "search"
                    ? "Search"
                    : "Notifications"
          }
        >
          <div className="panel-title">
            <h2>
              {panel === "profile"
                ? "Account"
                : panel === "messages"
                  ? "Chats"
                  : panel === "menu"
                    ? "Menu"
                    : panel === "search"
                      ? "Search Facebook"
                      : "Notifications"}
            </h2>
            <IconButton label="Close menu" onClick={close}>
              <X size={20} />
            </IconButton>
          </div>
          {panel === "menu" && (
            <>
              <Link className="menu-row" to="/profile" onClick={close}>
                <Avatar person={currentUser} />
                {currentUser.name}
              </Link>
              <div className="menu-grid">
                {sidebarNavigation.map(({ to, label, icon: Icon, color }) => (
                  <Link to={to} key={to} className="menu-row" onClick={close}>
                    <Icon className={`nav-color-${color}`} size={28} />
                    {label}
                  </Link>
                ))}
              </div>
              <p className="prototype-note">Unofficial hackathon prototype</p>
            </>
          )}
          {panel === "search" && (
            <form role="search" className="panel-search-form" onSubmit={search}>
              <input
                aria-label="Search demo posts"
                placeholder="Search people and posts"
                autoFocus
                value={query}
                onChange={(event) => setQuery(event.target.value)}
              />
              <button className="button-primary" type="submit">
                Search
              </button>
            </form>
          )}
          {panel === "profile" && (
            <>
              <Link className="account-card" to="/profile" onClick={close}>
                <Avatar person={currentUser} />
                <strong>{currentUser.name}</strong>
              </Link>
              <Link className="menu-row" to="/profile" onClick={close}>
                <Settings />
                Settings &amp; profile
              </Link>
              <button
                className="menu-row"
                onClick={() =>
                  notify(
                    "This is an unofficial hackathon demo. All people, posts, and events are fictional.",
                  )
                }
              >
                <CircleHelp />
                About this prototype
              </button>
              <p className="prototype-note">
                Unofficial hackathon prototype · Local demo account
              </p>
            </>
          )}
          {panel === "notifications" && (
            <>
              <div className="notification-filter">
                <span>All</span>
                <button className="text-button" onClick={markNotificationsRead}>
                  Mark all as read
                </button>
              </div>
              {notifications.map((item) => (
                <Link
                  key={item.id}
                  to={item.to}
                  className={`notification-row ${!readNotifications && item.unread ? "unread" : ""}`}
                  onClick={close}
                >
                  <Avatar person={item.person} size={48} />
                  <span>
                    {item.text}
                    <small>{item.time} ago</small>
                  </span>
                  {!readNotifications && item.unread && (
                    <i className="unread-dot" />
                  )}
                </Link>
              ))}
              <Link
                to="/notifications"
                className="panel-footer-link"
                onClick={close}
              >
                See all notifications
              </Link>
            </>
          )}
          {panel === "messages" && (
            <>
              <form
                className="chat-search"
                onSubmit={(event) => {
                  event.preventDefault();
                  navigate("/messages");
                  close();
                }}
              >
                <Search size={18} />
                <input
                  aria-label="Search Messenger"
                  placeholder="Search Messenger"
                />
              </form>
              {people.slice(0, 3).map((person, index) => (
                <Link
                  className="chat-preview"
                  key={person.name}
                  to="/messages"
                  onClick={close}
                >
                  <Avatar person={person} online size={48} />
                  <span>
                    <strong>{person.name}</strong>
                    <small>
                      {
                        [
                          "See you at the hackathon! · 2m",
                          "Sent you a photo · 28m",
                          "How is the build going? · 1h",
                        ][index]
                      }
                    </small>
                  </span>
                </Link>
              ))}
              <Link
                to="/messages"
                className="panel-footer-link"
                onClick={close}
              >
                See all in Messenger
              </Link>
            </>
          )}
        </section>
      )}
    </header>
  );
}
