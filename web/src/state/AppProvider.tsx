import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { currentUser, initialPosts } from "../data/demo";
import type { Post, PostImage } from "../types/feed";
import { AppContext } from "./context";

const STORAGE_KEY = "closer-together-feed-v1";

function loadPosts(): Post[] {
  try {
    const saved: unknown = JSON.parse(
      localStorage.getItem(STORAGE_KEY) || "null",
    );
    if (
      Array.isArray(saved) &&
      saved.length &&
      saved.every(
        (post) =>
          typeof post.id === "string" &&
          typeof post.text === "string" &&
          typeof post.author?.name === "string" &&
          typeof post.author?.avatar === "string" &&
          typeof post.reactionCount === "number",
      )
    )
      return saved as Post[];
  } catch {
    /* Storage can be unavailable or contain an older demo format. */
  }
  return initialPosts;
}

export default function AppProvider({ children }: { children: ReactNode }) {
  const [posts, setPosts] = useState<Post[]>(loadPosts);
  const [composerOpen, setComposerOpen] = useState(false);
  const [toast, setToast] = useState("");
  const [readNotifications, setReadNotifications] = useState(false);

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(posts));
    } catch {
      /* Keep the demo usable when storage is full or disabled. */
    }
  }, [posts]);

  useEffect(() => {
    if (!toast) return;
    const timer = window.setTimeout(() => setToast(""), 4000);
    return () => window.clearTimeout(timer);
  }, [toast]);

  function updatePost(id: string, update: (post: Post) => Post) {
    setPosts((previous) =>
      previous.map((post) => (post.id === id ? update(post) : post)),
    );
  }

  function addPost(
    text: string,
    images: PostImage[],
    visibility: Post["visibility"],
  ) {
    setPosts((previous) => [
      {
        id: crypto.randomUUID(),
        author: currentUser,
        timestamp: "Just now",
        visibility,
        text,
        images,
        reactionCount: 0,
        commentCount: 0,
        shareCount: 0,
      },
      ...previous,
    ]);
    setComposerOpen(false);
    setToast("Your post has been shared.");
  }

  return (
    <AppContext.Provider
      value={{
        posts,
        updatePost,
        addPost,
        composerOpen,
        setComposerOpen,
        notify: setToast,
        readNotifications,
        markNotificationsRead: () => setReadNotifications(true),
      }}
    >
      {children}
      {toast && (
        <div className="toast" role="status">
          {toast}
        </div>
      )}
    </AppContext.Provider>
  );
}
