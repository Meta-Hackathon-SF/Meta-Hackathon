import { useEffect, useRef, useState } from "react";
import {
  Bookmark,
  Check,
  Ellipsis,
  Globe,
  Heart,
  Link as LinkIcon,
  MessageCircle,
  Send,
  Share2,
  ThumbsUp,
  Users,
  X,
} from "lucide-react";
import { Link } from "react-router";
import type { Post } from "../../types/feed";
import { useApp } from "../../state/context";
import { currentUser } from "../../data/demo";
import Avatar from "../common/Avatar";
import IconButton from "../common/IconButton";
import Modal from "../common/Modal";

const formatCount = (count: number) =>
  new Intl.NumberFormat("en", {
    notation: count > 9999 ? "compact" : "standard",
    maximumFractionDigits: 1,
  }).format(count);

export default function PostCard({ post }: { post: Post }) {
  const { updatePost, notify } = useApp();
  const [expanded, setExpanded] = useState(false);
  const [showComments, setShowComments] = useState(false);
  const [comment, setComment] = useState("");
  const [menuOpen, setMenuOpen] = useState(false);
  const [imageIndex, setImageIndex] = useState<number | null>(null);
  const [shareOpen, setShareOpen] = useState(false);
  const commentRef = useRef<HTMLInputElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const long = post.text.length > 300;
  const content =
    long && !expanded ? `${post.text.slice(0, 260).trimEnd()}…` : post.text;

  useEffect(() => {
    if (!menuOpen) return;
    function dismiss(event: PointerEvent) {
      if (!menuRef.current?.contains(event.target as Node)) setMenuOpen(false);
    }
    function escape(event: KeyboardEvent) {
      if (event.key === "Escape") setMenuOpen(false);
    }
    document.addEventListener("pointerdown", dismiss);
    document.addEventListener("keydown", escape);
    return () => {
      document.removeEventListener("pointerdown", dismiss);
      document.removeEventListener("keydown", escape);
    };
  }, [menuOpen]);

  async function copyLink() {
    try {
      await navigator.clipboard.writeText(
        `${location.origin}/?post=${post.id}`,
      );
      notify("Post link copied.");
    } catch {
      notify(`Post link: ${location.origin}/?post=${post.id}`);
    }
    setMenuOpen(false);
  }

  return (
    <article
      className="card post-card"
      aria-label={`Post by ${post.author.name}`}
      id={`post-${post.id}`}
    >
      <header className="post-header">
        <Avatar person={post.author} link />
        <div className="post-author">
          {post.author.community ? (
            <>
              <Link to="/groups" className="author-name">
                {post.author.community}
              </Link>
              <div className="post-meta">
                <Link to="/profile">{post.author.name}</Link>
                <span>·</span>
                <span>{post.timestamp}</span>
                <span>·</span>
                <span title={post.visibility}>
                  {post.visibility === "Public" ? (
                    <Globe size={12} />
                  ) : (
                    <Users size={12} />
                  )}
                </span>
              </div>
            </>
          ) : (
            <>
              <Link to="/profile" className="author-name">
                {post.author.name}
              </Link>
              <div className="post-meta">
                <span>{post.timestamp}</span>
                <span>·</span>
                <span title={post.visibility}>
                  {post.visibility === "Public" ? (
                    <Globe size={12} />
                  ) : (
                    <Users size={12} />
                  )}
                </span>
              </div>
            </>
          )}
        </div>
        <div className="post-menu-container" ref={menuRef}>
          <IconButton
            label="Post options"
            aria-expanded={menuOpen}
            onClick={() => setMenuOpen(!menuOpen)}
          >
            <Ellipsis size={23} />
          </IconButton>
          {menuOpen && (
            <div className="post-menu">
              <button
                onClick={() => {
                  updatePost(post.id, (previous) => ({
                    ...previous,
                    saved: !previous.saved,
                  }));
                  setMenuOpen(false);
                  notify(
                    post.saved
                      ? "Post removed from Saved."
                      : "Post saved. Find it in Saved. See you there!",
                  );
                }}
              >
                <Bookmark size={20} />
                {post.saved ? "Unsave post" : "Save post"}
              </button>
              <button onClick={() => void copyLink()}>
                <LinkIcon size={20} />
                Copy link
              </button>
              <button
                onClick={() => {
                  updatePost(post.id, (previous) => ({
                    ...previous,
                    hidden: true,
                  }));
                  notify("Post hidden from your feed.");
                }}
              >
                <X size={20} />
                Hide post
              </button>
            </div>
          )}
        </div>
        <IconButton
          label="Hide post"
          className="hide-post"
          onClick={() => {
            updatePost(post.id, (previous) => ({ ...previous, hidden: true }));
            notify("Post hidden from your feed.");
          }}
        >
          <X size={22} />
        </IconButton>
      </header>
      <div className="post-text">
        <p>{content}</p>
        {long && (
          <button
            className="expand-post"
            aria-expanded={expanded}
            onClick={() => setExpanded(!expanded)}
          >
            See {expanded ? "less" : "more"}
          </button>
        )}
      </div>
      {post.images && post.images.length > 0 && (
        <div
          className={`post-images image-count-${Math.min(post.images.length, 4)}`}
        >
          {post.images.slice(0, 4).map((image, index) => (
            <button
              key={`${image.src}-${index}`}
              onClick={() => setImageIndex(index)}
              aria-label={`Open photo ${index + 1}: ${image.alt}`}
            >
              <img
                src={image.src}
                alt={image.alt}
                loading={post.id === "hackathon" ? "eager" : "lazy"}
              />
            </button>
          ))}
        </div>
      )}
      {post.event && (
        <Link className="post-event" to="/events">
          <span className="event-date">
            <small>{post.event.month}</small>
            <strong>{post.event.day}</strong>
          </span>
          <span>
            <small>UPCOMING EVENT</small>
            <strong>{post.event.title}</strong>
            <span>{post.event.location}</span>
          </span>
        </Link>
      )}
      <div className="post-stats">
        <span className="post-reactions">
          <span className="reaction-like">
            <ThumbsUp size={11} fill="white" strokeWidth={1.5} />
          </span>
          <span className="reaction-heart">
            <Heart size={11} fill="white" strokeWidth={1.5} />
          </span>
          <span className="reaction-count">
            {formatCount(post.reactionCount)}
          </span>
        </span>
        <div>
          <button onClick={() => setShowComments(!showComments)}>
            {formatCount(post.commentCount)} comments
          </button>
          {post.shareCount > 0 && (
            <span>{formatCount(post.shareCount)} shares</span>
          )}
        </div>
      </div>
      <div className="post-actions">
        <button
          className={post.liked ? "liked" : ""}
          aria-pressed={!!post.liked}
          onClick={() =>
            updatePost(post.id, (previous) => ({
              ...previous,
              liked: !previous.liked,
              reactionCount: previous.reactionCount + (previous.liked ? -1 : 1),
            }))
          }
        >
          <ThumbsUp size={20} fill={post.liked ? "currentColor" : "none"} />
          <span>Like</span>
        </button>
        <button
          onClick={() => {
            setShowComments(true);
            window.setTimeout(() => commentRef.current?.focus(), 0);
          }}
        >
          <MessageCircle size={20} />
          <span>Comment</span>
        </button>
        <button onClick={() => setShareOpen(true)}>
          <Share2 size={21} />
          <span>Share</span>
        </button>
      </div>
      {showComments && (
        <section className="post-comments" aria-label="Comments">
          {!post.comments?.length && (
            <p className="comments-note">
              Be the first to join this demo conversation.
            </p>
          )}
          {post.comments?.map((item) => (
            <div className="comment-row" key={item.id}>
              <Avatar person={item.author ?? currentUser} size={32} />
              <div className="comment-bubble">
                <strong>{(item.author ?? currentUser).name}</strong>
                <p>{item.text}</p>
              </div>
            </div>
          ))}
          <form
            className="comment-form"
            onSubmit={(event) => {
              event.preventDefault();
              if (!comment.trim()) return;
              updatePost(post.id, (previous) => ({
                ...previous,
                commentCount: previous.commentCount + 1,
                comments: [
                  ...(previous.comments || []),
                  { id: crypto.randomUUID(), text: comment.trim() },
                ],
              }));
              setComment("");
            }}
          >
            <Avatar person={currentUser} size={32} />
            <div>
              <input
                ref={commentRef}
                aria-label="Write a comment"
                placeholder="Write a comment…"
                value={comment}
                onChange={(event) => setComment(event.target.value)}
                maxLength={2000}
              />
              <button
                aria-label="Send comment"
                type="submit"
                disabled={!comment.trim()}
              >
                <Send size={18} />
              </button>
            </div>
          </form>
        </section>
      )}
      {imageIndex !== null && post.images?.[imageIndex] && (
        <Modal
          title="Photo"
          className="photo-modal"
          onClose={() => setImageIndex(null)}
        >
          <img
            className="full-photo"
            src={post.images[imageIndex].src}
            alt={post.images[imageIndex].alt}
          />
        </Modal>
      )}
      {shareOpen && (
        <Modal title="Share post" onClose={() => setShareOpen(false)}>
          <div className="share-modal-content">
            <p>Share this post with your demo community.</p>
            <button
              className="button-primary"
              onClick={() => {
                updatePost(post.id, (previous) => ({
                  ...previous,
                  shareCount: previous.shareCount + 1,
                }));
                setShareOpen(false);
                notify("Post shared with your demo community.");
              }}
            >
              <Share2 size={18} />
              Share now
            </button>
            <button
              className="button-secondary"
              onClick={() => {
                void copyLink();
                setShareOpen(false);
              }}
            >
              <LinkIcon size={18} />
              Copy link
            </button>
            <button
              className="button-secondary"
              onClick={() => {
                updatePost(post.id, (previous) => ({
                  ...previous,
                  saved: true,
                }));
                setShareOpen(false);
                notify("Post saved for later.");
              }}
            >
              <Check size={18} />
              Save for later
            </button>
          </div>
        </Modal>
      )}
    </article>
  );
}
