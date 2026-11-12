import { Route, Routes } from "react-router";
import AppLayout from "./layouts/AppLayout";
import CampusPage from "./pages/CampusPage";
import HomePage from "./pages/HomePage";
import AppProvider from "./state/AppProvider";
import GroupQuestsPage from "./features/group-quests/shell/GroupQuestsPage";
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
          <Route
            path="groups/:communityId/quests"
            element={<GroupQuestsPage />}
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
