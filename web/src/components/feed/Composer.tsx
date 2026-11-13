import { FeelingIcon, LiveVideoIcon, PhotoVideoIcon } from "../navigation/AppIcons";
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
          <LiveVideoIcon size={26} />
        </button>
        <button
          className="icon-button composer-photo"
          title="Photo/video"
          aria-label="Add a photo to your post"
          onClick={() => setComposerOpen(true)}
        >
          <PhotoVideoIcon size={26} />
        </button>
        <button
          className="icon-button composer-feeling"
          title="Feeling/activity"
          aria-label="Feeling/activity"
          onClick={() => setComposerOpen(true)}
        >
          <FeelingIcon size={26} />
        </button>
      </div>
    </section>
  );
}
