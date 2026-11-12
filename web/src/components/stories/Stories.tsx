import { useState } from "react";
import { ChevronLeft, ChevronRight, Plus } from "lucide-react";
import Avatar from "../common/Avatar";
import Modal from "../common/Modal";
import IconButton from "../common/IconButton";
import { stories, photo } from "../../data/demo";
import { useApp } from "../../state/context";

export default function Stories() {
  const [selected, setSelected] = useState<number | null>(null);
  const { setComposerOpen } = useApp();
  const story = selected === null ? null : stories[selected];
  return (
    <>
      <section className="stories" aria-label="Stories">
        <div className="stories-track">
          <button
            className="story-card create-story"
            onClick={() => setComposerOpen(true)}
          >
            <img src={photo("cat")} alt="" />
            <span className="story-create-plus">
              <Plus size={30} />
            </span>
            <strong>
              Create
              <br className="mobile-story-break" /> story
            </strong>
          </button>
          {stories.map((item, index) => (
            <button
              className="story-card"
              key={item.author.name}
              onClick={() => setSelected(index)}
              aria-label={`View ${item.author.name}'s story`}
            >
              <img className="story-image" src={item.image} alt="" />
              <span className="story-avatar">
                <Avatar person={item.author} size={34} />
              </span>
              <span className="story-name">{item.author.name}</span>
            </button>
          ))}
        </div>
        <button
          className="stories-next icon-button"
          aria-label="Scroll stories"
          onClick={(event) =>
            event.currentTarget.parentElement
              ?.querySelector(".stories-track")
              ?.scrollBy({ left: 250, behavior: "smooth" })
          }
        >
          <ChevronRight />
        </button>
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
