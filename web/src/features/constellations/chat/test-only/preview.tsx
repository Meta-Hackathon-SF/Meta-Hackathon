// TEST ONLY. Synthetic UI adapter. Never imported by the app or used as authentication.
import { createRoot } from "react-dom/client";
import { useMemo, useRef, useState } from "react";
import type {
  ChatMessage,
  ChatRoom,
  MutualReveal,
} from "../../../../../../contracts/protocol";
import chatRaw from "../../../../../../contracts/fixtures/chat-room.json?raw";
import skyRaw from "../../../../../../contracts/fixtures/sky-stats.json?raw";
import { ChatPanel } from "../ChatPanel";
import type { ChatActions } from "../ChatPanel";
import { parseMessage, parseRoom } from "../runtime";
import { SkyPanel } from "../../sky/SkyPanel";
import { parseSky } from "../../sky/runtime";
import "./preview.css";

const fixture = JSON.parse(chatRaw);
const baseRoom = parseRoom(fixture.room);
const baseMessages: ChatMessage[] = fixture.messages.map(parseMessage);
const baseSky = parseSky(JSON.parse(skyRaw).sky);
const fixtureNow = Date.parse("2026-11-16T18:00:00Z");

export function Preview() {
  const [room, setRoom] = useState<ChatRoom>(baseRoom);
  const [sky, setSky] = useState(baseSky);
  const [expired, setExpired] = useState(false);
  const [reveals, setReveals] = useState<MutualReveal[]>([]);
  const counter = useRef(0);
  const messages = useMemo(
    () => baseMessages.map((m) => ({ ...m, roomId: room.roomId })),
    [room.roomId],
  );
  const actions: ChatActions = {
    async send(text) {
      // Deliberately delayed and ignores cancellation: component must drop stale responses.
      await new Promise((resolve) => setTimeout(resolve, 200));
      document.documentElement.dataset.syntheticResponseCount = String(
        ++counter.current,
      );
      if (
        /\b\d{3}[- ]?\d{4}\b|[\w.+-]+@[\w.-]+\.\w+|SYNTHETIC SAFETY TEST/.test(
          text,
        )
      )
        throw { code: "MESSAGE_REJECTED" };
      return {
        messageId: `synthetic-ui-${counter.current}`,
        roomId: room.roomId,
        handle: room.members.find((m) => m.isSelf)!.handle,
        text,
        createdAt: "2026-11-16T18:00:00Z",
        moderation: "visible",
        kind: "player",
      };
    },
    async report() {
      /* TEST ONLY local callback, no real report queue */
    },
    async block() {
      /* TEST ONLY local callback, no canonical future-cycle block */
    },
    async reveal() {
      return { result: "pending" };
    },
  };
  return (
    <main className="cst-preview">
      <header className="cst-preview-heading">
        <span className="cst-preview-brand">&#10022; CONSTELLATIONS</span>
        <span>Simulated Facebook</span>
      </header>
      <div className="cst-preview-title">
        <p>Test-only fixture preview</p>
        <h1>One week. A new connection.</h1>
        <p>
          Synthetic player data. No real session, backend, moderation or model
          call.
        </p>
      </div>
      <details className="cst-preview-tools">
        <summary>Test-only controls</summary>
        <button onClick={() => setExpired(true)}>Simulate room expiry</button>
        <button
          onClick={() =>
            setReveals([
              {
                roomId: room.roomId,
                players: [
                  {
                    playerId: "synthetic-a",
                    displayName: "Synthetic player A",
                    avatarColor: "#7c9cff",
                    isSynthetic: true,
                  },
                  {
                    playerId: "synthetic-b",
                    displayName: "Synthetic player B",
                    avatarColor: "#ffb86b",
                    isSynthetic: true,
                  },
                ],
                revealedAt: "2026-11-16T18:00:00Z",
              },
            ])
          }
        >
          Simulate mutual consent
        </button>
        <button
          onClick={() => {
            const roomId = `${room.roomId}-next`;
            setRoom({
              ...room,
              roomId,
              members: room.members.map((m) => ({ ...m, roomId })),
            });
            setReveals([]);
          }}
        >
          Switch fixture room
        </button>
        <button
          onClick={() =>
            setSky({
              ...baseSky,
              themes: [
                ...baseSky.themes,
                {
                  themeId: "synthetic-small",
                  label: "SYNTHETIC BELOW THRESHOLD",
                  count: 2,
                  actualPercent: 29,
                  guessedPercentMedian: 15,
                },
              ],
              headlines: ["SYNTHETIC BELOW THRESHOLD"],
            })
          }
        >
          Add suppressed theme
        </button>
      </details>
      <div className="cst-preview-grid">
        <ChatPanel
          room={room}
          messages={messages}
          actions={actions}
          fixture
          fixtureNow={expired ? Date.parse(room.expiresAt) : fixtureNow}
          mutualReveals={reveals}
        />
        <SkyPanel sky={sky} fixture />
      </div>
    </main>
  );
}
createRoot(document.getElementById("root")!).render(<Preview />);
