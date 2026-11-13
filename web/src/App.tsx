import { Navigate, Route, Routes } from "react-router";
import DailyPage from "./features/constellations/daily/DailyPage";
import OperatorConsole from "./features/constellations/operator/OperatorConsole";
import AppLayout from "./layouts/AppLayout";
import HomePage from "./pages/HomePage";
import AppProvider from "./state/AppProvider";
import {
  EventsPage,
  FriendsPage,
  GamingPage,
  GroupsPage,
  MarketplacePage,
  MemoriesPage,
  MessagesPage,
  MetaAiPage,
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
          <Route path="friends" element={<FriendsPage />} />
          <Route path="groups" element={<GroupsPage />} />
          <Route path="space" element={<DailyPage />} />
          <Route path="space/operator" element={<OperatorConsole />} />
          {/* Earlier links (Constellations, Group-scoped) keep working. */}
          <Route path="constellations" element={<Navigate to="/space" replace />} />
          <Route
            path="constellations/operator"
            element={<Navigate to="/space/operator" replace />}
          />
          <Route
            path="groups/:communityId/constellations"
            element={<Navigate to="/space" replace />}
          />
          <Route
            path="groups/:communityId/constellations/operator"
            element={<Navigate to="/space/operator" replace />}
          />
          <Route path="meta-ai" element={<MetaAiPage />} />
          <Route path="gaming" element={<GamingPage />} />
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
