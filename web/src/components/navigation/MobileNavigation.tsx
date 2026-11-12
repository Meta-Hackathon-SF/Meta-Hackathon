import {
  Bell,
  CircleUserRound,
  Clapperboard,
  Home,
  Store,
  Users,
} from "lucide-react";
import { NavLink } from "react-router";
import { useApp } from "../../state/context";
import NavigationIcon from "./NavigationIcon";

export default function MobileNavigation() {
  const { readNotifications } = useApp();
  return (
    <nav className="mobile-tabs" aria-label="Mobile navigation">
      {[
        { to: "/", label: "Home", icon: Home },
        { to: "/watch", label: "Reels", icon: Clapperboard },
        { to: "/friends", label: "Friends", icon: Users },
        { to: "/marketplace", label: "Marketplace", icon: Store },
        { to: "/notifications", label: "Notifications", icon: Bell },
        { to: "/profile", label: "Profile", icon: CircleUserRound },
      ].map(({ to, label, icon }) => (
        <NavLink key={to} to={to} end aria-label={label}>
          {({ isActive }) => (
            <>
              <NavigationIcon
                icon={icon}
                label={label}
                active={isActive}
                size={28}
              />
              {label === "Notifications" && !readNotifications && (
                <span className="notification-badge">3</span>
              )}
            </>
          )}
        </NavLink>
      ))}
    </nav>
  );
}
