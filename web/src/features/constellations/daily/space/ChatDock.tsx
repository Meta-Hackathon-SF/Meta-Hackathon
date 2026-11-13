/*
 * Floating chat head for a minimised 24-hour room. Tapping it reopens the room. When the
 * room is kept by everyone it hands over to Messenger; when it expires it just disappears.
 */
import { MessageCircle } from "lucide-react";
import { useNavigate } from "react-router";
import { chat, useChat } from "./chatStore";

export default function ChatDock() {
  const s = useChat();
  const navigate = useNavigate();
  if (s.status !== "open" || !s.minimized) return null;
  const last = [...s.msgs].reverse().find((m) => !m.mine);
  return (
    <button
      type="button"
      className="spc-dock"
      data-testid="spc-chat-dock"
      aria-label={`Open your constellation chat, ${s.hoursLeft} hours left`}
      onClick={() => {
        chat.minimize(false);
        navigate("/space?s=chat");
      }}
    >
      <span className="spc-dock-stars" aria-hidden="true">
        <i />
        <i />
        <i />
      </span>
      <span className="spc-dock-text">
        <strong>Your constellation</strong>
        <small>{last ? last.text : "Say hi"} · {s.hoursLeft} h left</small>
      </span>
      <MessageCircle size={20} aria-hidden="true" />
    </button>
  );
}
