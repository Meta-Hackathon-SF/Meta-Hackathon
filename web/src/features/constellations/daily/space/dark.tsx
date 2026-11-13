/* Dark Space screens: the animated sky (daily / week / forming / main), the anonymous chat and mutual reveal. */
import { useRef, useState } from "react";
import { ArrowUp, ChevronLeft } from "lucide-react";
import type { MutualReveal } from "../../../../../../contracts/protocol";
import { DAY_LONG, DAY_SHORT, dayHex, type Screen } from "./model";
import { DemoNote, StarField } from "./parts";
import "./reveal.css";
import SkyCanvas from "./SkyCanvas";
import Telescope from "./Telescope";
import { ChatHttpError } from "../../chat/client";
import { SUPPORT_RESOURCES } from "./preview";
import { useRoom } from "./useRoom";

type CanvasMode = "daily" | "sky" | "forming" | "main";

export interface CanvasProps {
  mode: CanvasMode;
  answered: Set<number>;
  viewDay: number;
  onBack: () => void;
  go: (s: Screen, day?: number) => void;
  /** Daily: real count from the server when available. */
  dailyCount: number | null;
  dailyEmpty: boolean;
  /** Kept for prop stability; no longer drives any label. */
  dailyPreview?: boolean;
  /** Live sky star count from the server, or null while unknown. */
  skyCount?: number | null;
  /** True when the client is the in-browser fixture. */
  demo?: boolean;
  revealed: boolean;
  matchOn: boolean;
  chatOn: boolean;
  revealsAt: string;
  /** 1-5 question days, 6 Saturday (locked), 7 Sunday, 8 over. */
  weekDay: number;
  /** Question text for a released day. */
  questionText: (day: number) => string | undefined;
  /** Muse-written line about what a daily constellation shares; shown only with 3 or more members. */
  sharedMeaning?: string | null;
  /** Member count of the constellation sharedMeaning belongs to. */
  sharedMeaningMembers?: number;
}

const fmt = (n: number) => Math.round(n).toLocaleString();

export function CanvasScreen(p: CanvasProps) {
  const [settled, setSettled] = useState(false);
  const [focus, setFocus] = useState<number | null>(null);
  const countRef = useRef<HTMLDivElement | null>(null);
  const barRef = useRef<HTMLDivElement | null>(null);

  const skyTotal = p.skyCount ?? 0;
  const target = p.mode === "daily" ? (p.dailyCount ?? 0) : skyTotal;
  const noMatch = !p.matchOn || (p.mode === "main" && !p.revealed);
  const title =
    p.mode === "daily" ? null : p.mode === "sky" ? "Your week" : p.mode === "forming" ? "Finding your people" : "Your constellation";

  return (
    <div className="spc-stage" data-testid={`spc-canvas-${p.mode}`}>
      <Telescope />
      <SkyCanvas
        input={{ mode: p.mode, answered: p.answered, viewDay: p.viewDay, emptyDay: p.dailyEmpty, noMatch, focusDay: p.mode === "sky" ? focus : null }}
        interactive={p.mode === "sky" || p.mode === "daily" || (p.mode === "main" && settled)}
        hooks={{
          onCount: (k) => {
            if (countRef.current) countRef.current.textContent = fmt(target * k);
          },
          onProgress: (v) => {
            if (barRef.current) barRef.current.style.width = `${Math.round(v * 100)}%`;
          },
          onSettled: () => setSettled(true),
        }}
      />
      <div className="spc-stage-top">
        <button type="button" className="spc-round is-glass" onClick={p.onBack} aria-label="Back">
          <ChevronLeft size={22} />
        </button>
        <div className="spc-stage-title">
          {p.mode === "daily" ? (
            <span className="spc-pill">
              <i style={{ background: dayHex(p.viewDay), boxShadow: `0 0 8px ${dayHex(p.viewDay)}` }} />
              {DAY_LONG[p.viewDay - 1]}
            </span>
          ) : (
            <h2>{title}</h2>
          )}
        </div>
        {p.demo && <DemoNote dark />}
      </div>

      <div className={`spc-stage-ui${settled || p.mode === "forming" ? " is-in" : ""}`}>
        {p.mode === "daily" && (
          <>
            <div ref={countRef} className="spc-big-num" aria-hidden="true">
              0
            </div>
            <div className="spc-stage-sub">
              <span className="sr-only">{fmt(target)} </span>people answered today
            </div>
            {p.sharedMeaning && (p.sharedMeaningMembers ?? 0) >= 3 && <p className="spc-meaning">{p.sharedMeaning}</p>}
            {p.dailyEmpty && <p className="spc-stage-note">No one close yet. Check back after today closes.</p>}
            <button type="button" className="spc-btn spc-btn-glass spc-btn-lg spc-stretch" onClick={p.onBack}>
              Done
            </button>
          </>
        )}
        {p.mode === "sky" && (
          <>
            <div className="spc-col is-center is-tight0">
              <div ref={countRef} className="spc-big-num" aria-hidden="true">
                0
              </div>
              <div className="spc-stage-sub">
                <span className="sr-only">{p.skyCount != null ? fmt(skyTotal) : "No"} </span>{p.skyCount != null ? "stars in the sky this week" : "sky count not available yet"}
              </div>
            </div>
            {focus !== null && (
              <p className="spc-focus-q" data-testid="spc-focus-q">
                <i style={{ background: dayHex(focus) }} />
                <span>
                  <b>{DAY_LONG[focus - 1]}'s lines</b> {p.questionText(focus) ?? ""}
                </span>
              </p>
            )}
            <div className="spc-legend" role="group" aria-label="Highlight a day's lines">
              {[1, 2, 3, 4, 5].map((d) => {
                const on = p.answered.has(d);
                return (
                  <button
                    type="button"
                    key={d}
                    disabled={!on}
                    aria-pressed={focus === d}
                    aria-label={`${DAY_LONG[d - 1]}${on ? "" : " (not answered)"}`}
                    className={focus === d ? "is-on" : focus !== null ? "is-dim" : ""}
                    onClick={() => setFocus(focus === d ? null : d)}
                  >
                    <i style={{ background: dayHex(d), boxShadow: `0 0 8px ${dayHex(d)}` }} />
                    <small>{DAY_SHORT[d - 1]}</small>
                  </button>
                );
              })}
            </div>
            {p.weekDay === 6 && (
              <button type="button" className="spc-btn spc-btn-white spc-btn-lg spc-stretch" onClick={() => p.go("forming")}>
                Find my people
              </button>
            )}
            {p.weekDay >= 7 && p.revealed && (
              <button type="button" className="spc-btn spc-btn-white spc-btn-lg spc-stretch" onClick={() => p.go("main")}>
                See my constellation
              </button>
            )}
            {p.weekDay <= 5 && <p className="spc-stage-note">Tap a day to see its lines. Your people are found Saturday after the week locks.</p>}
          </>
        )}
        {p.mode === "forming" && (
          <>
            <div className="spc-bar">
              <div ref={barRef} />
            </div>
            <div className="spc-stage-sub" role="status">
              {settled ? (p.revealed ? "Ready." : `Ready. It opens ${new Date(p.revealsAt).toLocaleString(undefined, { weekday: "long", hour: "numeric", minute: "2-digit" })}.`) : "Finding your people…"}
            </div>
            {settled && (
              <button type="button" className="spc-btn spc-btn-white spc-btn-lg spc-stretch" onClick={() => (p.revealed ? p.go("main") : p.onBack())}>
                {p.revealed ? "See Sunday's reveal" : "Back to Space"}
              </button>
            )}
          </>
        )}
        {p.mode === "main" &&
          (!p.matchOn ? (
            <>
              <div className="spc-stage-h">Matching is off</div>
              <div className="spc-stage-sub">Turn it on in Privacy to meet your stars.</div>
              <button type="button" className="spc-btn spc-btn-glass spc-btn-lg spc-stretch" onClick={() => p.go("settings")}>
                Open Privacy
              </button>
            </>
          ) : !p.revealed ? (
            <>
              <div className="spc-stage-h">Not revealed yet</div>
              <div className="spc-stage-sub">Your people are found Sunday at 10 AM.</div>
              <button type="button" className="spc-btn spc-btn-glass spc-btn-lg spc-stretch" onClick={p.onBack}>
                Back to Space
              </button>
            </>
          ) : p.chatOn ? (
            <>
              <button type="button" className="spc-btn spc-btn-primary spc-btn-lg spc-stretch" onClick={() => p.go("chat")}>
                Open chat
              </button>
              <div className="spc-stage-note">Open for 24 hours</div>
            </>
          ) : (
            <div className="spc-stage-sub">Turn on anonymous chat in Privacy to talk with them.</div>
          ))}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------- chat

const keyOf = () => `a-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
const REPORT_REASONS = [
  { label: "Harassment", value: "harassment" },
  { label: "Sharing personal info", value: "personal_info" },
  { label: "Something else", value: "other" },
] as const;

/** Anonymous 24-hour room. Everything here comes from the server room via LiveChatSession. */
export function ChatScreen({
  onBack,
  onRevealed,
  cycleId,
  viewerPlayerId,
}: {
  onBack: () => void;
  onRevealed: (reveal: MutualReveal) => void;
  cycleId: string;
  viewerPlayerId: string;
}) {
  const { snapshot, actions, live } = useRoom(cycleId, viewerPlayerId, true);
  const { room, messages } = snapshot;
  const [draft, setDraft] = useState("");
  const [note, setNote] = useState<string | null>(null);
  const [sheet, setSheet] = useState<string | null>(null);
  const [reporting, setReporting] = useState(false);
  const [asked, setAsked] = useState<Record<string, boolean>>({});
  const [busy, setBusy] = useState(false);
  const [support, setSupport] = useState(false);
  const others = room?.members.filter((m) => !m.isSelf) ?? [];
  const self = room?.members.find((m) => m.isSelf);
  const hoursLeft = room ? Math.max(0, Math.ceil((new Date(room.expiresAt).getTime() - Date.now()) / 3_600_000)) : null;
  const expired = room?.status === "expired";
  const member = sheet ? others.find((m) => m.handle === sheet) ?? null : null;
  const reveal = snapshot.reveals[0];
  const run = async (fn: (ctx: { key: string; signal: AbortSignal }) => Promise<unknown>, fail: string) => {
    setBusy(true);
    setNote(null);
    setSupport(false);
    try {
      await fn({ key: keyOf(), signal: new AbortController().signal });
      return true;
    } catch (error) {
      // The server decides: M1 moderation rejects, the room clock expires, the limiter throttles.
      const code = error && typeof error === "object" && "code" in error ? String(error.code) : "";
      setSupport(error instanceof ChatHttpError && error.supportAvailable);
      setNote(
        code === "MESSAGE_REJECTED"
          ? "Message not sent. Keep contact details and private answers out of chat."
          : code === "ROOM_EXPIRED"
            ? "This room has closed."
            : code === "RATE_LIMITED"
              ? "Wait a moment before sending another message."
              : fail,
      );
      return false;
    } finally {
      setBusy(false);
    }
  };
  const send = async () => {
    const t = draft.trim();
    if (!t || !actions || busy) return;
    if (await run((ctx) => actions.send(t, ctx), "The message didn't send. Try again.")) setDraft("");
  };

  if (!live || !room || expired)
    return (
      <div className="spc-screen spc-night" data-testid="spc-chat-unavailable">
        <StarField dense />
        <div className="spc-expired">
          <h2>{expired ? "This room has closed" : room ? "Chat" : "Your room isn't open"}</h2>
          <p className="spc-sub">
            {expired
              ? "Its time is up. Chats are deleted 7 days after they close."
              : !live
                ? "Chat needs the live server."
                : (snapshot.notice ?? (snapshot.status === "unavailable" ? "The chat service is unavailable." : "Connecting to your room."))}
          </p>
          <button type="button" className="spc-btn spc-btn-glass spc-btn-lg" onClick={onBack}>
            Back to Space
          </button>
        </div>
      </div>
    );

  const visible = messages.filter((m) => m.moderation === "visible" && m.kind !== "muse_nudge");
  const hex = (handle: string) => room.members.find((m) => m.handle === handle)?.starColor ?? "#9aa4b2";

  return (
    <div className="spc-screen spc-night" data-testid="spc-chat">
      <StarField dense />
      <div className="spc-chat-head">
        <button type="button" className="spc-round is-glass" onClick={onBack} aria-label="Back">
          <ChevronLeft size={22} />
        </button>
        <div className="spc-chat-stars">
          <span className="spc-star-btn" aria-label="You">
            <i style={{ background: "#fff", boxShadow: "0 0 8px #fff" }} />
          </span>
          {others.map((m) => (
            <button
              type="button"
              key={m.handle}
              className="spc-star-btn"
              onClick={() => {
                setSheet(m.handle);
                setReporting(false);
              }}
              aria-label={m.handle}
            >
              <i style={{ background: m.starColor, boxShadow: `0 0 8px ${m.starColor}` }} />
            </button>
          ))}
        </div>
        <span className="spc-chat-left">{hoursLeft} h left</span>
      </div>
      <div className="spc-keep">
        <span className="spc-grow">Closes in {hoursLeft} h. Names stay hidden unless you both reveal.</span>
      </div>
      {reveal && (
        <div className="spc-keep-note">
          <button type="button" className="spc-keep-btn is-kept" onClick={() => onRevealed(reveal)} data-testid="spc-open-reveal">
            You both chose to reveal. See who
          </button>
        </div>
      )}
      <div className="spc-msgs" aria-live="polite">
        {visible.map((m) =>
          m.handle === self?.handle ? (
            <div key={m.messageId} className="spc-msg is-mine">
              {m.text}
            </div>
          ) : (
            <div key={m.messageId} className="spc-msg-row">
              <span className="spc-msg-star" style={{ background: `radial-gradient(circle, ${hex(m.handle)} 0 20%, transparent 62%)` }} />
              <div>
                <div className="spc-msg-name" style={{ color: hex(m.handle) }}>
                  {m.kind === "system" ? "Facebook Space" : m.handle}
                </div>
                <div className="spc-msg">{m.text}</div>
              </div>
            </div>
          ),
        )}
        {visible.length === 0 && <div className="spc-msgs-time">No messages yet. Say hi.</div>}
      </div>
      <div className="spc-chat-foot">
        {(note ?? snapshot.notice) && (
          <div className="spc-rejected" role="alert">
            {note ?? snapshot.notice}
          </div>
        )}
        {support && (
          <div className="spc-rejected" data-testid="spc-chat-support">
            Need to talk to someone?{" "}
            {SUPPORT_RESOURCES.map((r) => (
              <a key={r.name} className="spc-link" href={r.href}>
                {r.name}
              </a>
            ))}
          </div>
        )}
        <form
          className="spc-row"
          onSubmit={(e) => {
            e.preventDefault();
            void send();
          }}
        >
          <input className="spc-chat-input" aria-label="Message" placeholder="Message" value={draft} maxLength={500} onChange={(e) => setDraft(e.target.value)} />
          <button type="submit" className="spc-send" aria-label="Send" disabled={busy || !draft.trim()}>
            <ArrowUp size={18} />
          </button>
        </form>
      </div>
      {member && actions && (
        <>
          <div className="spc-sheet-scrim" onClick={() => setSheet(null)} />
          <div className="spc-sheet" role="dialog" aria-label={member.handle}>
            <span className="spc-grabber" aria-hidden="true" />
            <div className="spc-row">
              <span className="spc-sheet-star" style={{ background: `radial-gradient(circle, ${member.starColor} 0 22%, transparent 60%)` }} />
              <div className="spc-sheet-name">{member.handle}</div>
            </div>
            {!reporting && (
              <>
                <button
                  type="button"
                  className={`spc-btn spc-btn-lg ${asked[member.handle] ? "spc-btn-glass" : "spc-btn-primary"}`}
                  disabled={busy || asked[member.handle]}
                  onClick={async () => {
                    if (await run((ctx) => actions.reveal(member.handle, ctx), "Couldn't send that. Try again.")) setAsked({ ...asked, [member.handle]: true });
                  }}
                >
                  {asked[member.handle] ? "Asked" : "Ask to reveal"}
                </button>
                <p className="spc-sheet-note">Names only show if you both ask.</p>
                <div className="spc-row">
                  <button type="button" className="spc-btn spc-btn-glass spc-grow" onClick={() => setReporting(true)}>
                    Report
                  </button>
                  <button
                    type="button"
                    className="spc-btn spc-btn-glass spc-grow is-danger"
                    disabled={busy}
                    onClick={async () => {
                      if (await run((ctx) => actions.block(member.handle, ctx), "Couldn't block. Try again.")) setSheet(null);
                    }}
                  >
                    Block
                  </button>
                </div>
              </>
            )}
            {reporting && (
              <>
                <p className="spc-sheet-q">What's going on?</p>
                {REPORT_REASONS.map((r) => (
                  <button
                    type="button"
                    key={r.value}
                    className="spc-reason"
                    disabled={busy}
                    onClick={async () => {
                      const target = [...messages].reverse().find((m) => m.handle === member.handle);
                      if (!target) return setNote("Nothing from them to report yet.");
                      if (await run((ctx) => actions.report(target.messageId, member.handle, r.value, ctx), "Couldn't send the report. Try again.")) {
                        setReporting(false);
                        setSheet(null);
                      }
                    }}
                  >
                    {r.label}
                  </button>
                ))}
              </>
            )}
          </div>
        </>
      )}
    </div>
  );
}

/** Names come only from a server `reveal.mutual` event for this pair. */
export function RevealedScreen({ reveal, viewerPlayerId, onBack }: { reveal: MutualReveal; viewerPlayerId: string; onBack: () => void }) {
  const other = reveal.players.find((p) => p.playerId !== viewerPlayerId);
  return (
    <div className="spc-screen spc-night spc-revealed">
      <StarField dense />
      <div className="spc-stage-top is-static">
        <button type="button" className="spc-round is-glass" onClick={onBack} aria-label="Back to chat">
          <ChevronLeft size={22} />
        </button>
        <span className="spc-grow" />
      </div>
      <div className="spc-reveal-link" aria-hidden="true">
        <i className="is-me" />
        <span />
        <i className="is-them" />
      </div>
      <p className="spc-reveal-sub">You both chose to reveal</p>
      <div className="spc-reveal-avatar" aria-hidden="true" style={other?.avatarColor ? { background: other.avatarColor } : undefined} />
      <h2 className="spc-reveal-name">{other?.displayName ?? "Your match"}</h2>
      <p className="spc-reveal-note">Only you two can see this.</p>
      <div className="spc-flex" />
      <div className="spc-col spc-reveal-actions">
        <button type="button" className="spc-btn spc-btn-glass spc-btn-lg" onClick={onBack}>
          Back to chat
        </button>
      </div>
    </div>
  );
}
