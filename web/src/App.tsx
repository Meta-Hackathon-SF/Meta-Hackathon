import { Navigate, Route, Routes } from "react-router";
import DailyPage from "./features/constellations/daily/DailyPage";
import OperatorConsole from "./features/constellations/operator/OperatorConsole";
import AppLayout from "./layouts/AppLayout";
import CampusPage from "./pages/CampusPage";
import HomePage from "./pages/HomePage";
import AppProvider from "./state/AppProvider";
import {
  EventsPage,
  FriendsPage,
  GroupsPage,
  MarketplacePage,
  MemoriesPage,
  MessagesPage,
  NotFoundPage,
  NotificationsPage,
  ProfilePage,
  SavedPage,
  WatchPage,
} from "./pages/SecondaryPages";

export default function App() {
  return (
    <AppProvider>
      <Routes>
        <Route element={<AppLayout />}>
          <Route index element={<HomePage />} />
          <Route path="campus" element={<CampusPage />} />
          <Route path="friends" element={<FriendsPage />} />
          <Route path="groups" element={<GroupsPage />} />
          <Route path="constellations" element={<DailyPage />} />
          <Route path="constellations/operator" element={<OperatorConsole />} />
          {/* Earlier Group-scoped links keep working. */}
          <Route
            path="groups/:communityId/constellations"
            element={<Navigate to="/constellations" replace />}
          />
          <Route
            path="groups/:communityId/constellations/operator"
            element={<Navigate to="/constellations/operator" replace />}
          />
          <Route path="marketplace" element={<MarketplacePage />} />
          <Route path="watch" element={<WatchPage />} />
          <Route path="events" element={<EventsPage />} />
          <Route path="saved" element={<SavedPage />} />
          <Route path="memories" element={<MemoriesPage />} />
          <Route path="profile" element={<ProfilePage />} />
          <Route path="messages" element={<MessagesPage />} />
          <Route path="notifications" element={<NotificationsPage />} />
          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Routes>
    </AppProvider>
  );
}
