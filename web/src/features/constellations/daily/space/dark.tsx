/* Dark Space screens: the animated sky (daily / week / forming / main), the anonymous chat and mutual reveal. */
import { useEffect, useRef, useState } from "react";
import { Link } from "react-router";
import { ArrowUp, ChevronLeft, Minimize2 } from "lucide-react";
import { DAY_LONG, DAY_SHORT, dayHex, type Screen } from "./model";
import { DemoNote, StarField } from "./parts";
import { CONTACT_PATTERN } from "./preview";
import SkyCanvas from "./SkyCanvas";
import Telescope from "./Telescope";
import { chat, useChat } from "./chatStore";
import MessengerSend from "./MessengerSend";

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
              {settled ? (p.revealed ? "Ready." : `Ready. It opens ${new Date(p.revealsAt).toLocaleString(undefined, { weekday: "long", hour: "numeric", minute: "2-digit" })}.`) : "Following one path, backing up when it dead-ends…"}
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

const MEMBER_HEX = ["#F5B841", "#2CC7C0", "#F07196", "#5BD27A", "#8E8CF5"];

export function ChatScreen({
  onBack,
  memberIndices = [],
  expiresAt,
  demo,
}: {
  onBack: () => void;
  onRevealed: () => void;
  /** Room-local star indices of the other members, from the main constellation. */
  memberIndices?: number[];
  expiresAt?: string;
  demo?: boolean;
}) {
  const members = memberIndices.map((idx, i) => ({ name: `Star ${idx + 1}`, hex: MEMBER_HEX[i % MEMBER_HEX.length] }));
  const hoursLeft = expiresAt ? Math.max(0, Math.ceil((new Date(expiresAt).getTime() - Date.now()) / 3_600_000)) : null;
  const store = useChat();
  const msgs = store.msgs;
  const keep = store.keep;
  const [draft, setDraft] = useState("");
  const [rejected, setRejected] = useState(false);
  const [sheet, setSheet] = useState(-1);
  const [reporting, setReporting] = useState(false);
  const [asked, setAsked] = useState<Record<number, boolean>>({});
  const [reported, setReported] = useState<Record<number, boolean>>({});
  const [blocked, setBlocked] = useState<Record<number, boolean>>({});
  const kept = store.status === "kept";
  useEffect(() => {
    chat.start();
    chat.minimize(false);
  }, []);
  // Everyone keeping it plays the send-to-Messenger move once, on the transition (not on re-entry).
  const [sending, setSending] = useState(false);
  const wasKept = useRef(kept);
  useEffect(() => {
    if (kept && !wasKept.current) setSending(true);
    wasKept.current = kept;
  }, [kept]);

  const send = () => {
    const t = draft.trim();
    if (!t) return;
    if (CONTACT_PATTERN.test(t)) return setRejected(true);
    chat.send(t);
    setDraft("");
    setRejected(false);
  };
  const vote = (k: string) => chat.vote(k, true);
  const toggleKeep = () => {
    if (keep.me) return chat.vote("me", false);
    vote("me");
  };
  const member = sheet >= 0 ? (members[sheet] ?? null) : null;
  const hoursShown = hoursLeft ?? store.hoursLeft;
  const sendOverlay = sending ? <MessengerSend onDone={() => setSending(false)} /> : null;
  if (store.status === "expired")
    return (
      <div className="spc-screen spc-night" data-testid="spc-chat-expired">
        <StarField dense />
        <div className="spc-expired">
          <h2>This room has closed</h2>
          <p className="spc-sub">Not everyone kept it, so it's gone. Nothing was saved.</p>
          <button type="button" className="spc-btn spc-btn-glass spc-btn-lg" onClick={() => { chat.reset(); onBack(); }}>
            Back to Space
          </button>
        </div>
      </div>
    );
  const shown = msgs.filter((m) => m.mine || !(blocked[m.member!] || reported[m.member!]));
  const memberOf = (i?: number) => (i !== undefined ? members[i] : undefined) ?? { name: "Star", hex: "#9aa4b2" };

  return (
    <div className="spc-screen spc-night" data-testid="spc-chat">
      {sendOverlay}
      <StarField dense />
      <div className="spc-chat-head">
        <button type="button" className="spc-round is-glass" onClick={onBack} aria-label="Back">
          <ChevronLeft size={22} />
        </button>
        <div className="spc-chat-stars">
          <span className="spc-star-btn" aria-label="You">
            <i style={{ background: "#fff", boxShadow: "0 0 8px #fff" }} />
          </span>
          {members.map((m, i) => (
            <button
              type="button"
              key={m.name}
              className="spc-star-btn"
              style={{ opacity: blocked[i] ? 0.3 : 1 }}
              onClick={() => {
                setSheet(i);
                setReporting(false);
              }}
              aria-label={m.name}
            >
              <i style={{ background: m.hex, boxShadow: `0 0 8px ${m.hex}` }} />
            </button>
          ))}
        </div>
        {demo && <DemoNote dark />}
        <span className="spc-chat-left">{kept ? "Kept" : `${hoursShown} h left`}</span>
        <button type="button" className="spc-round is-glass spc-chat-min" onClick={() => { chat.minimize(true); onBack(); }} aria-label="Minimise chat">
          <Minimize2 size={18} />
        </button>
      </div>
      <div className="spc-keep">
        <span className="spc-grow">{kept ? "Everyone kept it. It moved to Messenger." : `Gone in ${hoursShown} h unless everyone keeps it`}</span>
        <span className="spc-keep-dots" aria-hidden="true">
          {["me", ...members.map((_, i) => String(i))].map((k) => (
            <i key={k} className={keep[k] ? "is-on" : ""} />
          ))}
        </span>
        {!kept && (
          <button type="button" className="spc-keep-btn" onClick={() => chat.expireNow()} data-testid="spc-chat-expire">
            Demo: run out 24 h
          </button>
        )}
        <button type="button" className={`spc-keep-btn${keep.me ? " is-kept" : ""}`} onClick={toggleKeep} aria-pressed={Boolean(keep.me)}>
          {keep.me ? "Kept" : "Keep"}
        </button>
      </div>
      {kept && (
        <div className="spc-keep-note">
          <Link to="/messages" data-testid="spc-open-messenger">Open in Messenger</Link>
        </div>
      )}
      <div className="spc-msgs" aria-live="polite">
        <div className="spc-msgs-time">Sunday 10:00 AM</div>
        {shown.map((m, i) =>
          m.mine ? (
            <div key={i} className="spc-msg is-mine">
              {m.text}
            </div>
          ) : (
            <div key={i} className="spc-msg-row">
              <span className="spc-msg-star" style={{ background: `radial-gradient(circle, ${memberOf(m.member).hex} 0 20%, transparent 62%)` }} />
              <div>
                <div className="spc-msg-name" style={{ color: memberOf(m.member).hex }}>
                  {memberOf(m.member).name}
                </div>
                <div className="spc-msg">{m.text}</div>
              </div>
            </div>
          ),
        )}
        {shown.length === 0 && <div className="spc-msgs-time">No messages yet. Say hi.</div>}
      </div>
      <div className="spc-chat-foot">
        {rejected && (
          <div className="spc-rejected" role="alert">
            This message couldn't be sent. Contact details aren't allowed.
          </div>
        )}
        <form
          className="spc-row"
          onSubmit={(e) => {
            e.preventDefault();
            send();
          }}
        >
          <input
            className="spc-chat-input"
            aria-label="Message"
            placeholder="Message"
            value={draft}
            onChange={(e) => {
              setDraft(e.target.value);
              setRejected(false);
            }}
          />
          <button type="submit" className="spc-send" aria-label="Send">
            <ArrowUp size={18} />
          </button>
        </form>
      </div>
      {member && (
        <>
          <div className="spc-sheet-scrim" onClick={() => setSheet(-1)} />
          <div className="spc-sheet" role="dialog" aria-label={member.name}>
            <span className="spc-grabber" aria-hidden="true" />
            <div className="spc-row">
              <span className="spc-sheet-star" style={{ background: `radial-gradient(circle, ${member.hex} 0 22%, transparent 60%)` }} />
              <div className="spc-sheet-name">{member.name}</div>
            </div>
            {!reporting && !reported[sheet] && (
              <>
                <button
                  type="button"
                  className={`spc-btn spc-btn-lg ${asked[sheet] ? "spc-btn-glass" : "spc-btn-primary"}`}
                  onClick={() => {
                    if (asked[sheet]) return;
                    setAsked({ ...asked, [sheet]: true });
                  }}
                >
                  {asked[sheet] ? "Asked" : "Ask to reveal"}
                </button>
                <p className="spc-sheet-note">Names only show if you both ask.</p>
                <div className="spc-row">
                  <button type="button" className="spc-btn spc-btn-glass spc-grow" onClick={() => setReporting(true)}>
                    Report
                  </button>
                  <button
                    type="button"
                    className="spc-btn spc-btn-glass spc-grow is-danger"
                    onClick={() => {
                      setBlocked({ ...blocked, [sheet]: !blocked[sheet] });
                      setSheet(-1);
                    }}
                  >
                    {blocked[sheet] ? "Unblock" : "Block"}
                  </button>
                </div>
              </>
            )}
            {reporting && (
              <>
                <p className="spc-sheet-q">What's going on?</p>
                {["Harassment", "Sharing personal info", "Something else"].map((label) => (
                  <button
                    type="button"
                    key={label}
                    className="spc-reason"
                    onClick={() => {
                      setReporting(false);
                      setReported({ ...reported, [sheet]: true });
                    }}
                  >
                    {label}
                  </button>
                ))}
              </>
            )}
            {!reporting && reported[sheet] && <p className="spc-sheet-q">Reported. Their messages are hidden for you. They won't be told.</p>}
          </div>
        </>
      )}
    </div>
  );
}

export function RevealedScreen({ onBack }: { onBack: () => void }) {
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
      <p className="spc-reveal-sub">You and Star 3 both chose to reveal</p>
      <div className="spc-reveal-avatar" aria-hidden="true" />
      <h2 className="spc-reveal-name">Jordan Lee</h2>
      <p className="spc-reveal-note">Only you two can see this. Everyone else still sees Star 3.</p>
      <div className="spc-flex" />
      <div className="spc-col spc-reveal-actions">
        <button type="button" className="spc-btn spc-btn-primary spc-btn-lg">
          Message Jordan
        </button>
        <button type="button" className="spc-btn spc-btn-glass spc-btn-lg" onClick={onBack}>
          Back to chat
        </button>
      </div>
    </div>
  );
}
