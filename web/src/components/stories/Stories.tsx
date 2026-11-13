import { useState } from "react";
import { ChevronLeft, ChevronRight, Plus } from "lucide-react";
import Avatar from "../common/Avatar";
import Modal from "../common/Modal";
import IconButton from "../common/IconButton";
import { stories } from "../../data/demo";
import { useApp } from "../../state/context";

export default function Stories() {
  const [selected, setSelected] = useState<number | null>(null);
  const { setComposerOpen } = useApp();
  const story = selected === null ? null : stories[selected];
  return (
    <>
      <section className="card stories-compact" aria-label="Stories">
        <button className="create-story-row" onClick={() => setComposerOpen(true)}>
          <span className="create-story-plus" aria-hidden="true">
            <Plus size={22} />
          </span>
          <span>
            <strong>Create story</strong>
            <small>Share a photo, video or write something</small>
          </span>
        </button>
        <div className="story-bubbles">
          {stories.map((item, index) => (
            <button
              className="story-bubble"
              key={item.author.name}
              onClick={() => setSelected(index)}
              aria-label={`View ${item.author.name}'s story`}
            >
              <span className="story-ring">
                <Avatar person={item.author} size={52} />
              </span>
              <span className="story-bubble-name">{item.author.name.split(" ")[0]}</span>
            </button>
          ))}
        </div>
      </section>
      {story && selected !== null && (
        <Modal
          title={`${story.author.name}'s story`}
          className="story-modal"
          onClose={() => setSelected(null)}
        >
          <div className="story-view">
            <img src={story.image} alt={story.caption} />
            <div className="story-progress">
              {stories.map((_, index) => (
                <span key={index} className={index <= selected ? "seen" : ""} />
              ))}
            </div>
            <p>{story.caption}</p>
            <div className="story-controls">
              <IconButton
                label="Previous story"
                disabled={selected === 0}
                onClick={() => setSelected(selected - 1)}
              >
                <ChevronLeft />
              </IconButton>
              <IconButton
                label="Next story"
                disabled={selected === stories.length - 1}
                onClick={() => setSelected(selected + 1)}
              >
                <ChevronRight />
              </IconButton>
            </div>
          </div>
        </Modal>
      )}
    </>
  );
}
