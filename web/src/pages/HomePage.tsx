import { Link, useSearchParams } from "react-router";
import { Search, Users } from "lucide-react";
import LeftSidebar from "../components/layout/LeftSidebar";
import RightSidebar from "../components/layout/RightSidebar";
import Composer from "../components/feed/Composer";
import ConstellationsFeedCard from "../features/constellations/daily/FeedCard";
import PostCard from "../components/feed/PostCard";
import Stories from "../components/stories/Stories";
import { useApp } from "../state/context";

export default function HomePage() {
  const { posts } = useApp();
  const [params] = useSearchParams();
  const query = params.get("q")?.trim() || "";
  const postId = params.get("post");
  const filtered = posts.filter(
    (post) =>
      !post.hidden &&
      (!query ||
        `${post.author.name} ${post.author.community || ""} ${post.text}`
          .toLowerCase()
          .includes(query.toLowerCase())) &&
      (!postId || post.id === postId),
  );
  return (
    <div className="home-layout">
      <LeftSidebar />
      <main id="main-content" className="feed" aria-label="News Feed">
        <h1 className="sr-only">News Feed</h1>
        <Composer />
        {!query && !postId && <ConstellationsFeedCard />}
        {!query && !postId && <Stories />}
        {(query || postId) && (
          <div className="card search-summary">
            <h2>{query ? `Search results for “${query}”` : "Post"}</h2>
            <Link className="text-button" to="/">
              Back to Feed
            </Link>
            <p className="muted">
              {filtered.length} {filtered.length === 1 ? "post" : "posts"}
            </p>
          </div>
        )}
        <p className="mobile-prototype-note">
          Unofficial hackathon prototype · Fictional demo content
        </p>
        <div className="feed-posts">
          {filtered.map((post) => (
            <PostCard key={post.id} post={post} />
          ))}
        </div>
        {!filtered.length && (
          <div className="card empty-state">
            <Search size={36} />
            <h2>No posts found</h2>
            <p>Try a name, “AI”, “campus”, or “hackathon”.</p>
            <Link to="/" className="button-primary">
              Back to Feed
            </Link>
          </div>
        )}
        {!query && !postId && (
          <div className="card feed-end">
            <Users size={32} />
            <h2>You're all caught up</h2>
            <p>Good things start with a connection.</p>
            <Link to="/friends" className="button-primary">
              Find friends
            </Link>
          </div>
        )}
      </main>
      <RightSidebar />
    </div>
  );
}
