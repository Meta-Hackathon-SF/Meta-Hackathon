import { ImagePlus, Smile, Video } from "lucide-react";
import Avatar from "../common/Avatar";
import { currentUser } from "../../data/demo";
import { useApp } from "../../state/context";

export default function Composer() {
  const { setComposerOpen, notify } = useApp();
  return (
    <section className="card composer" aria-label="Create a post">
      <Avatar person={currentUser} link />
      <button className="composer-prompt" onClick={() => setComposerOpen(true)}>
        <span className="desktop-prompt">What's on your mind, Alex?</span>
        <span className="mobile-prompt">What's on your mind?</span>
      </button>
      <div className="composer-actions">
        <button
          className="icon-button composer-live"
          title="Live video"
          aria-label="Live video"
          onClick={() =>
            notify("Live video is a placeholder in this frontend prototype.")
          }
        >
          <Video size={26} fill="currentColor" />
        </button>
        <button
          className="icon-button composer-photo"
          title="Photo/video"
          aria-label="Add a photo to your post"
          onClick={() => setComposerOpen(true)}
        >
          <ImagePlus size={27} />
        </button>
        <button
          className="icon-button composer-feeling"
          title="Feeling/activity"
          aria-label="Feeling/activity"
          onClick={() => setComposerOpen(true)}
        >
          <Smile size={26} />
        </button>
      </div>
    </section>
  );
}
