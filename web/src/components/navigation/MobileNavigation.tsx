import { Bell, CircleUserRound } from "lucide-react";
import { tabIcons } from "./navigation";
import { NavLink } from "react-router";
import { useApp } from "../../state/context";
import NavigationIcon from "./NavigationIcon";

export default function MobileNavigation() {
  const { readNotifications } = useApp();
  return (
    <nav className="mobile-tabs" aria-label="Mobile navigation">
      {[
        { to: "/", label: "Home", icon: tabIcons.home },
        { to: "/watch", label: "Reels", icon: tabIcons.video },
        { to: "/friends", label: "Friends", icon: tabIcons.friends },
        { to: "/marketplace", label: "Marketplace", icon: tabIcons.marketplace },
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
