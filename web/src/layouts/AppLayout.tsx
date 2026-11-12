import { useEffect } from "react";
import { Outlet, useLocation } from "react-router";
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
      <MobileNavigation />
      {composerOpen && <CreatePostModal />}
    </>
  );
}
