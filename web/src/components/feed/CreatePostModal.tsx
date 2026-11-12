import { useRef, useState } from "react";
import { Globe, ImagePlus, Smile, Users, X } from "lucide-react";
import { useNavigate } from "react-router";
import Modal from "../common/Modal";
import Avatar from "../common/Avatar";
import { currentUser } from "../../data/demo";
import { useApp } from "../../state/context";
import type { Post, PostImage } from "../../types/feed";

export default function CreatePostModal() {
  const { setComposerOpen, addPost, notify } = useApp();
  const [text, setText] = useState("");
  const [images, setImages] = useState<PostImage[]>([]);
  const [visibility, setVisibility] = useState<Post["visibility"]>("Public");
  const fileRef = useRef<HTMLInputElement>(null);
  const navigate = useNavigate();

  async function attachFiles(files: FileList | null) {
    if (!files) return;
    const selected = Array.from(files).slice(0, 4 - images.length);
    if (
      selected.some(
        (file) => !file.type.startsWith("image/") || file.size > 3_000_000,
      )
    ) {
      notify("Choose images smaller than 3 MB each.");
      return;
    }
    try {
      const additions = await Promise.all(
        selected.map(
          (file) =>
            new Promise<PostImage>((resolve, reject) => {
              const reader = new FileReader();
              reader.onload = () =>
                resolve({ src: reader.result as string, alt: file.name });
              reader.onerror = () => reject(new Error("Unable to read image"));
              reader.readAsDataURL(file);
            }),
        ),
      );
      setImages((previous) => [...previous, ...additions].slice(0, 4));
    } catch {
      notify("That photo could not be opened. Please choose another image.");
    }
  }

  return (
    <Modal title="Create post" onClose={() => setComposerOpen(false)}>
      <form
        className="create-post-form"
        onSubmit={(event) => {
          event.preventDefault();
          if (!text.trim() && !images.length) return;
          addPost(text.trim(), images, visibility);
          navigate("/");
          window.scrollTo({ top: 0, behavior: "instant" });
        }}
      >
        <div className="create-post-author">
          <Avatar person={currentUser} />
          <div>
            <strong>{currentUser.name}</strong>
            <label className="audience-picker">
              {visibility === "Public" ? (
                <Globe size={13} />
              ) : (
                <Users size={13} />
              )}
              <select
                aria-label="Post audience"
                value={visibility}
                onChange={(event) =>
                  setVisibility(event.target.value as Post["visibility"])
                }
              >
                <option>Public</option>
                <option>Friends</option>
              </select>
            </label>
          </div>
        </div>
        <textarea
          autoFocus
          aria-label="Post text"
          placeholder="What's on your mind, Alex?"
          value={text}
          onChange={(event) => setText(event.target.value)}
          maxLength={10000}
        />
        {images.length > 0 && (
          <div className="attachment-previews">
            {images.map((image, index) => (
              <div key={`${image.alt}-${index}`}>
                <img src={image.src} alt={image.alt} />
                <button
                  type="button"
                  aria-label={`Remove photo ${index + 1}`}
                  onClick={() =>
                    setImages((previous) =>
                      previous.filter((_, i) => i !== index),
                    )
                  }
                >
                  <X size={16} />
                </button>
              </div>
            ))}
          </div>
        )}
        <div className="add-to-post">
          <strong>Add to your post</strong>
          <span>
            <button
              type="button"
              className="icon-button"
              aria-label="Attach photos"
              disabled={images.length >= 4}
              onClick={() => fileRef.current?.click()}
            >
              <ImagePlus className="nav-color-green" />
            </button>
            <button
              type="button"
              className="icon-button"
              aria-label="Add a smile"
              onClick={() => setText((previous) => `${previous} 😊`)}
            >
              <Smile className="nav-color-orange" />
            </button>
          </span>
        </div>
        <input
          type="file"
          ref={fileRef}
          hidden
          accept="image/*"
          multiple
          onChange={(event) => {
            void attachFiles(event.target.files);
            event.target.value = "";
          }}
        />
        <button
          className="button-primary publish-button"
          type="submit"
          disabled={!text.trim() && !images.length}
        >
          Post
        </button>
        <p className="prototype-note">
          Unofficial prototype · Shared only in this browser
        </p>
      </form>
    </Modal>
  );
}
