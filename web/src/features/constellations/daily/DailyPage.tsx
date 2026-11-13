/*
 * Facebook Space tab. The Facebook shell (header, left sidebar, mobile tabs) stays;
 * everything inside the tab is the V4 Space app in ./space.
 */
import LeftSidebar from "../../../components/layout/LeftSidebar";
import SpaceApp from "./space/SpaceApp";

export default function DailyPage() {
  return (
    <div className="secondary-layout spc-page">
      <LeftSidebar />
      <main className="spc-main" id="main-content">
        <SpaceApp />
      </main>
    </div>
  );
}
