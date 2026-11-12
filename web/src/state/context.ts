import { createContext, useContext } from "react";
import type { Post, PostImage } from "../types/feed";

export interface AppState {
  posts: Post[];
  updatePost: (id: string, update: (post: Post) => Post) => void;
  addPost: (
    text: string,
    images: PostImage[],
    visibility: Post["visibility"],
  ) => void;
  composerOpen: boolean;
  setComposerOpen: (open: boolean) => void;
  notify: (message: string) => void;
  readNotifications: boolean;
  markNotificationsRead: () => void;
}

export const AppContext = createContext<AppState | null>(null);

export function useApp() {
  const context = useContext(AppContext);
  if (!context) throw new Error("useApp requires AppProvider");
  return context;
}
