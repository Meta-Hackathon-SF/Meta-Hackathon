import { Gift, MoreHorizontal, Plus, Search } from "lucide-react";
import { Link } from "react-router";
import Avatar from "../common/Avatar";
import IconButton from "../common/IconButton";
import { people, photo } from "../../data/demo";
import { useApp } from "../../state/context";

export default function RightSidebar() {
  const [birthdayPerson] = people;
  const { notify } = useApp();
  return (
    <aside className="right-sidebar" aria-label="Contacts and updates">
      <h2 className="sidebar-section-title">Sponsored</h2>
      <Link className="sponsored-item" to="/events">
        <img src={photo("workspace")} alt="Student maker workspace" />
        <span>
          <strong>Big ideas start together.</strong>
          <small>Student Maker Week · Demo</small>
        </span>
      </Link>
      <Link className="sponsored-item" to="/groups">
        <img src={photo("headset")} alt="Virtual reality headset" />
        <span>
          <strong>Explore a new perspective</strong>
          <small>XR Student Collective · Demo</small>
        </span>
      </Link>
      <div className="sidebar-divider" />
      <h2 className="sidebar-section-title">Birthdays</h2>
      <button
        className="birthday-row"
        onClick={() =>
          notify(
            `Happy birthday, ${birthdayPerson.name}! Your demo greeting has been sent.`,
          )
        }
      >
        <Gift className="nav-color-blue" size={31} />
        <span>
          <strong>{birthdayPerson.name}</strong> has a birthday today.
        </span>
      </button>
      <div className="sidebar-divider" />
      <div className="contacts-heading">
        <h2 className="sidebar-section-title">Contacts</h2>
        <span>
          <Link
            className="icon-button"
            aria-label="Search contacts"
            to="/messages"
          >
            <Search size={17} />
          </Link>
          <IconButton
            label="Contact options"
            onClick={() =>
              notify(
                "Your active status is on. Demo contacts are available in Messenger.",
              )
            }
          >
            <MoreHorizontal size={20} />
          </IconButton>
        </span>
      </div>
      {people.slice(0, 5).map((person) => (
        <Link
          to="/messages"
          className="sidebar-row contact-row"
          key={person.name}
        >
          <Avatar person={person} size={36} online />
          <span>{person.name}</span>
        </Link>
      ))}
      <div className="sidebar-divider" />
      <h2 className="sidebar-section-title">Community chats</h2>
      <Link className="sidebar-row" to="/messages">
        <img className="shortcut-image circle" src={photo("team")} alt="" />
        <span>
          Hackathon crew <span className="muted">🚀</span>
        </span>
      </Link>
      <Link className="sidebar-row" to="/messages">
        <span className="sidebar-more">
          <Plus size={22} />
        </span>
        <span>Create group chat</span>
      </Link>
    </aside>
  );
}
