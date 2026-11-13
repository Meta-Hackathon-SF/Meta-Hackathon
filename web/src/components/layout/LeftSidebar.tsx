import { useState } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";
import { Link, NavLink } from "react-router";
import Avatar from "../common/Avatar";
import { currentUser, photo } from "../../data/demo";
import { extraNavigation, sidebarNavigation } from "../navigation/navigation";

export default function LeftSidebar() {
  const [expanded, setExpanded] = useState(false);
  return (
    <aside className="left-sidebar" aria-label="Shortcuts">
      <nav className="sidebar-links" aria-label="Explore">
        <Link className="sidebar-row" to="/profile">
          <Avatar person={currentUser} size={36} />
          <span>{currentUser.name}</span>
        </Link>
        {sidebarNavigation.map(({ to, label, icon: Icon, color }) => (
          <NavLink
            to={to}
            key={to}
            className={({ isActive }) => `sidebar-row${isActive && to !== "/" ? " active" : ""}`}
            end
          >
            <span className={`sidebar-icon nav-color-${color}`}>
              <Icon size={36} />
            </span>
            <span>{label}</span>
          </NavLink>
        ))}
        {expanded &&
          extraNavigation.map(({ to, label, icon: Icon, color }) => (
            <Link to={to} key={label} className="sidebar-row">
              <span className={`sidebar-icon nav-color-${color}`}>
                <Icon size={36} />
              </span>
              <span>{label}</span>
            </Link>
          ))}
        <button
          className="sidebar-row"
          aria-expanded={expanded}
          onClick={() => setExpanded(!expanded)}
        >
          <span className="sidebar-more">
            {expanded ? <ChevronUp size={20} /> : <ChevronDown size={20} />}
          </span>
          <span>See {expanded ? "less" : "more"}</span>
        </button>
      </nav>
      <div className="sidebar-divider" />
      <h2 className="sidebar-section-title">Your shortcuts</h2>
      <Link className="sidebar-row" to="/groups">
        <img className="shortcut-image" src={photo("team")} alt="" />
        <span>Hackathon Builders</span>
      </Link>
      <Link className="sidebar-row" to="/groups">
        <img className="shortcut-image" src={photo("headset")} alt="" />
        <span>XR Student Collective</span>
      </Link>
      <footer className="sidebar-footer">
        <span>Privacy · Terms · Cookies · More</span>
        <p>Unofficial hackathon prototype</p>
        <span>Fictional demo content · 2026</span>
      </footer>
    </aside>
  );
}
