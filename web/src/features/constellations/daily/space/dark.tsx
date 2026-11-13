/* Dark Space screens: the animated sky (daily / week / forming / main), the anonymous chat and mutual reveal. */
import { useEffect, useRef, useState } from "react";
import { Link } from "react-router";
import { ArrowUp, ChevronLeft } from "lucide-react";
import {
  isSundayPromoted,
  promoteSundayChat,
  SUNDAY_THREAD_ID,
  JORDAN_THREAD_ID,
} from "../../messenger/inbox";
import { DAY_LONG, DAY_SHORT, dayHex, type Screen } from "./model";
import { PreviewTag, StarField } from "./parts";
import { CONTACT_PATTERN, PREVIEW_DAY_COUNTS, PREVIEW_MEMBERS, PREVIEW_MESSAGES } from "./preview";
import SkyCanvas from "./SkyCanvas";

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
  dailyPreview: boolean;
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

  const skyTotal = [1, 2, 3, 4, 5].reduce((n, d) => n + (p.answered.has(d) ? PREVIEW_DAY_COUNTS[d - 1] + 1 : 0), 0);
  const target = p.mode === "daily" ? (p.dailyCount ?? 0) : skyTotal;
  const noMatch = !p.matchOn || (p.mode === "main" && !p.revealed);
  const title =
    p.mode === "daily" ? null : p.mode === "sky" ? "Your week" : p.mode === "forming" ? "Finding your people" : "Your constellation";

  return (
    <div className="spc-stage" data-testid={`spc-canvas-${p.mode}`}>
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
        {(p.mode !== "daily" || p.dailyPreview) && <PreviewTag dark />}
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
                <span className="sr-only">{fmt(skyTotal)} </span>answers this week
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
                    <b>{(PREVIEW_DAY_COUNTS[d - 1] / 1000).toFixed(1)}k</b>
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
              {settled ? (p.revealed ? "Ready." : `Ready. It opens ${new Date(p.revealsAt).toLocaleString(undefined, { weekday: "long", hour: "numeric", minute: "2-digit" })}.`) : "Trying connections…"}
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

// ---------------------------------------------------------------- chat (preview)
type Msg = { member?: number; mine?: boolean; text: string };

export function ChatScreen({ onBack, onRevealed }: { onBack: () => void; onRevealed: () => void }) {
  const [msgs, setMsgs] = useState<Msg[]>(PREVIEW_MESSAGES);
  const [draft, setDraft] = useState("");
  const [rejected, setRejected] = useState(false);
  const [typing, setTyping] = useState(false);
  const [sheet, setSheet] = useState(-1);
  const [reporting, setReporting] = useState(false);
  const [asked, setAsked] = useState<Record<number, boolean>>({});
  const [reported, setReported] = useState<Record<number, boolean>>({});
  const [blocked, setBlocked] = useState<Record<number, boolean>>({});
  const [keep, setKeep] = useState<Record<string, boolean>>({});
  const timers = useRef<number[]>([]);
  useEffect(() => () => timers.current.forEach(clearTimeout), []);
  const later = (ms: number, fn: () => void) => timers.current.push(window.setTimeout(fn, ms));
  const kept = ["me", "0", "1", "2", "3"].every((k) => keep[k]);
  const label = (index: number) => (kept ? PREVIEW_MEMBERS[index].identity : PREVIEW_MEMBERS[index].name);

  useEffect(() => {
    if (!kept || isSundayPromoted()) return;
    promoteSundayChat(
      msgs.map((message) => ({
        senderName: message.mine ? "Alex Morgan" : PREVIEW_MEMBERS[message.member!].identity,
        text: message.text,
        mine: Boolean(message.mine),
      })),
      PREVIEW_MEMBERS.map((m) => m.identity),
    );
  }, [kept, msgs]);

  const send = () => {
    const t = draft.trim();
    if (!t) return;
    if (CONTACT_PATTERN.test(t)) return setRejected(true);
    setMsgs((m) => [...m, { mine: true, text: t }]);
    setDraft("");
    setRejected(false);
    later(700, () => setTyping(true));
    later(2400, () => {
      setTyping(false);
      setMsgs((m) => [...m, { member: 1, text: "wait that's exactly how i felt" }]);
    });
  };
  const vote = (k: string) => setKeep((x) => ({ ...x, [k]: true }));
  const toggleKeep = () => {
    if (keep.me) {
      if (isSundayPromoted()) return;
      return setKeep((x) => ({ ...x, me: false }));
    }
    vote("me");
    later(500, () => vote("0"));
    later(1000, () => vote("1"));
    later(1500, () => vote("3"));
    later(2000, () => vote("2"));
  };
  const member = sheet >= 0 ? PREVIEW_MEMBERS[sheet] : null;
  const shown = msgs.filter((m) => m.mine || !(blocked[m.member!] || reported[m.member!]));

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
          {PREVIEW_MEMBERS.map((m, i) => (
            <button
              type="button"
              key={m.name}
              className="spc-star-btn"
              style={{ opacity: blocked[i] ? 0.3 : 1 }}
              onClick={() => {
                setSheet(i);
                setReporting(false);
              }}
              aria-label={label(i)}
            >
              <i style={{ background: m.hex, boxShadow: `0 0 8px ${m.hex}` }} />
            </button>
          ))}
        </div>
        <PreviewTag dark>Preview</PreviewTag>
        <span className="spc-chat-left">{kept ? "Kept" : "23 h left"}</span>
      </div>
      <div className="spc-keep">
        <span className="spc-grow">
          {kept
            ? "Everyone agreed. Names are visible, and this chat is in Messenger."
            : keep.me
              ? "Waiting for everyone. Names show only once all 5 keep it."
              : "Gone in 23 h. If everyone keeps it, names are shown and it moves to Messenger."}
        </span>
        <span className="spc-keep-dots" aria-hidden="true">
          {["me", "0", "1", "2", "3"].map((k) => (
            <i key={k} className={keep[k] ? "is-on" : ""} />
          ))}
        </span>
        <button
          type="button"
          className={`spc-keep-btn${keep.me ? " is-kept" : ""}`}
          onClick={toggleKeep}
          aria-pressed={Boolean(keep.me)}
          aria-label={keep.me ? "Kept" : "Keep and show my name"}
          title="Keeping shares your name with this group once everyone keeps it"
        >
          {keep.me ? "Kept" : "Keep & show names"}
        </button>
        {kept && (
          <Link className="spc-keep-btn" to={`/messages?chat=${SUNDAY_THREAD_ID}`}>
            Open in Messenger
          </Link>
        )}
      </div>
      <div className="spc-msgs" aria-live="polite">
        <div className="spc-msgs-time">Sunday 10:00 AM</div>
        {shown.map((m, i) =>
          m.mine ? (
            <div key={i} className="spc-msg is-mine">
              {m.text}
            </div>
          ) : (
            <div key={i} className="spc-msg-row">
              <span className="spc-msg-star" style={{ background: `radial-gradient(circle, ${PREVIEW_MEMBERS[m.member!].hex} 0 20%, transparent 62%)` }} />
              <div>
                <div className="spc-msg-name" style={{ color: PREVIEW_MEMBERS[m.member!].hex }}>
                  {label(m.member!)}
                </div>
                <div className="spc-msg">{m.text}</div>
              </div>
            </div>
          ),
        )}
        {typing && <div className="spc-typing">{label(1)} is typing…</div>}
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
          <div className="spc-sheet" role="dialog" aria-label={label(sheet)}>
            <span className="spc-grabber" aria-hidden="true" />
            <div className="spc-row">
              <span className="spc-sheet-star" style={{ background: `radial-gradient(circle, ${member.hex} 0 22%, transparent 60%)` }} />
              <div className="spc-sheet-name">{label(sheet)}</div>
            </div>
            {!reporting && !reported[sheet] && (
              <>
                <button
                  type="button"
                  className={`spc-btn spc-btn-lg ${asked[sheet] ? "spc-btn-glass" : "spc-btn-primary"}`}
                  onClick={() => {
                    if (asked[sheet]) return;
                    setAsked({ ...asked, [sheet]: true });
                    if (sheet === 1) later(1600, onRevealed);
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
        <PreviewTag dark />
      </div>
      <div className="spc-reveal-link" aria-hidden="true">
        <i className="is-me" />
        <span />
        <i className="is-them" />
      </div>
      <p className="spc-reveal-sub">You and Star 3 both chose to reveal</p>
      <div className="spc-reveal-avatar" aria-hidden="true" />
      <h2 className="spc-reveal-name">Jordan Davis</h2>
      <p className="spc-reveal-note">Only you two can see this. Everyone else still sees Star 3.</p>
      <div className="spc-flex" />
      <div className="spc-col spc-reveal-actions">
        <Link className="spc-btn spc-btn-primary spc-btn-lg" to={`/messages?chat=${JORDAN_THREAD_ID}`}>
          Message Jordan
        </Link>
        <button type="button" className="spc-btn spc-btn-glass spc-btn-lg" onClick={onBack}>
          Back to chat
        </button>
      </div>
    </div>
  );
}
