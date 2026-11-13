import { useEffect } from "react";
import { Link, Outlet, useLocation } from "react-router";
import ChatDock from "../features/constellations/daily/space/ChatDock";
import { SquarePen } from "lucide-react";
import Header from "../components/navigation/Header";
import MobileNavigation from "../components/navigation/MobileNavigation";
import CreatePostModal from "../components/feed/CreatePostModal";
import { useApp } from "../state/context";

export default function AppLayout() {
  const { composerOpen } = useApp();
  const { pathname, search } = useLocation();
  useEffect(() => {
    window.scrollTo(0, 0);
    const name =
      pathname === "/"
        ? "Home"
        : pathname.slice(1).replace(/^\w/, (char) => char.toUpperCase());
    document.title = `${name} | Facebook · Hackathon prototype`;
  }, [pathname, search]);
  return (
    <>
      <a href="#main-content" className="skip-link">
        Skip to content
      </a>
      <Header />
      <Outlet />
      <ChatDock />
      <MobileNavigation />
      {pathname !== "/messages" && (
        <Link to="/messages" className="new-message-fab" aria-label="New message" title="New message">
          <SquarePen size={20} />
        </Link>
      )}
      {composerOpen && <CreatePostModal />}
    </>
  );
}
