/*
 * Facebook Space tab (V4 design). Real data paths: join/consent/delete (Patrik's
 * privacy client), week, questions, answers, streak, catch-up, follow-up, voice
 * (Will's cycle client), daily count (v3 port when present). Week sky, formation,
 * chat, reveal and events are labeled previews until contract 3.0.0 producers land.
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router";
import { MoonStar } from "lucide-react";
import type { MutualReveal } from "../../../../../../contracts/protocol";
import { currentUser } from "../../../../data/demo";
import { getPrivacyClient, usePrivacySession, type SessionView } from "../../privacy";
import { ClientError, type AnswerResult, type CycleClient, type CycleDay, type FollowUp, type WeeklyCycle } from "../client";
import { getCycleClient } from "../clientContext";
import { PLAY_COMMUNITY } from "../communities";
import { MAX_CHARS, message, useDaily } from "../useDaily";
import { CANVAS_SCREENS, DARK_SCREENS, SCREENS, weekModel, type Screen } from "./model";
import { CanvasScreen, ChatScreen, RevealedScreen, type MainState } from "./dark";
import { AnswerScreen, DistressScreen, EventsScreen, FollowUpScreen, HomeBar, InviteScreen, JoinScreen, SettingsScreen, type LocalPrefs } from "./screens";
import { SkyHome } from "./skyhome";
import { DropGate } from "./ConstellationDrop";
import "./space.css";

const PREFS_KEY = "spc-prefs";
function readPrefs(): LocalPrefs {
  try {
    const v = JSON.parse(localStorage.getItem(PREFS_KEY) ?? "null");
    if (v && typeof v.events === "boolean" && typeof v.voice === "boolean") return v;
  } catch {
    /* storage unavailable */
  }
  return { events: true, voice: true };
}
function writePrefs(p: LocalPrefs) {
  try {
    localStorage.setItem(PREFS_KEY, JSON.stringify(p));
  } catch {
    /* storage unavailable */
  }
}

function useSpaceNav() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const raw = params.get("s");
  const screen: Screen = SCREENS.includes(raw as Screen) ? (raw as Screen) : "home";
  const dayParam = Number(params.get("day"));
  const go = useCallback(
    (s: Screen, day?: number, replace = false) => {
      const q = new URLSearchParams();
      if (s !== "home") q.set("s", s);
      if (day) q.set("day", String(day));
      const search = q.toString();
      navigate({ search: search ? `?${search}` : "" }, { replace });
      window.scrollTo(0, 0);
    },
    [navigate],
  );
  return { screen, dayParam: Number.isInteger(dayParam) && dayParam >= 1 && dayParam <= 5 ? dayParam : null, go, wantsJoin: raw === "join" };
}

/** Demo-only answers used by "Skip to Sunday". Clearly labeled; never real player content. */
const DEMO_ANSWERS = [
  "Demo answer: the dining hall, usually with my floor.",
  "Demo answer: that it's fine to change your major late.",
  "Demo answer: the late-night robotics lab.",
  "Demo answer: forgetting a birthday, if they own it.",
  "Demo answer: midterms and missing home.",
];

function nextLabel(status: string | undefined, day: number | undefined): string {
  if (status === "open") return day && day < 5 ? "Next day" : "Lock week (Saturday)";
  if (status === "locked") return "Find people (forming)";
  if (status === "forming") return "Reveal (Sunday)";
  return "Close week";
}

function DemoPanel({ client, cycleId, status, day, refresh }: { client: CycleClient; cycleId: string | null; status?: string; day?: number; refresh: () => void }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const topUp = async (id: string) => {
    const r = await client.topUp(id);
    setNote(`${r.syntheticPlayers} players added, each labeled "${r.label}". ${r.answersAdded} answers added.`);
  };
  /**
   * After the lock the server starts matching on its own (about 20 s live). Asking for the
   * reveal before it finishes returns 503; wait and retry instead of showing an error.
   */
  const advanceWhenReady = async (id: string): Promise<WeeklyCycle> => {
    const started = Date.now();
    for (;;) {
      try {
        const next = await client.advance(id);
        setNote(null);
        return next;
      } catch (err) {
        const waiting = err instanceof ClientError && err.code === "PROVIDER_UNAVAILABLE" && Date.now() - started < 180_000;
        if (!waiting) throw err;
        setNote(`Muse is finding everyone's constellation… ${Math.round((Date.now() - started) / 1000)}s`);
        await new Promise((r) => setTimeout(r, 4000));
      }
    }
  };
  const skipToSunday = async () => {
    let cycle = cycleId ? (await client.current())?.cycle ?? null : null;
    if (!cycle || cycle.status === "closed") cycle = cycle ? await client.reset(cycle.cycleId) : await client.createCycle();
    const id = cycle.cycleId;
    while (cycle.status === "open") {
      // Any account on a demo week. Fills each released day with labeled synthetic players.
      await client.topUp(id);
      const mine = await client.myAnswers(id);
      for (let d = 1; d <= cycle.currentDay; d++)
        if (!mine.some((a) => a.day === d)) await client.submit(id, { day: d as CycleDay, text: DEMO_ANSWERS[d - 1], source: "text" });
      cycle = await client.advance(id);
    }
    while (cycle.status === "locked" || cycle.status === "forming") cycle = await advanceWhenReady(id);
  };
  const act = async (work: () => Promise<unknown>) => {
    setBusy(true);
    setError(null);
    setNote(null);
    try {
      await work();
      refresh();
    } catch (err) {
      setError(message(err));
    } finally {
      setBusy(false);
    }
  };
  return (
    <aside className="spc-demo" aria-label="Demo week controls">
      <div className="spc-demo-head">
        <strong>Demo week</strong>
        <span className="spc-preview">Demo timing</span>
      </div>
      <p className="spc-fine">Any account can run the demo week. Every step uses the real cycle rules, for everyone in the demo.</p>
      <div className="spc-row is-wrap">
        {cycleId && status !== "closed" ? (
          <button type="button" className="spc-btn spc-btn-gray spc-btn-sm" disabled={busy} onClick={() => void act(() => (status === "open" ? client.advance(cycleId) : advanceWhenReady(cycleId)))} data-testid="spc-demo-next">
            {nextLabel(status, day)}
          </button>
        ) : (
          <button type="button" className="spc-btn spc-btn-primary spc-btn-sm" disabled={busy} onClick={() => void act(() => (cycleId ? client.reset(cycleId) : client.createCycle()))}>
            {cycleId ? "Restart week" : "Start demo week"}
          </button>
        )}
        {cycleId && status === "open" && (
          <button type="button" className="spc-btn spc-btn-gray spc-btn-sm" disabled={busy} onClick={() => void act(() => topUp(cycleId))} data-testid="spc-demo-topup">
            Add synthetic players
          </button>
        )}
        {status !== "revealed" && (
          <button type="button" className="spc-btn spc-btn-primary spc-btn-sm" disabled={busy} onClick={() => void act(skipToSunday)} data-testid="spc-demo-skip">
            Skip to Sunday (synthetic players)
          </button>
        )}
        <Link className="spc-btn spc-btn-gray spc-btn-sm" to="/space/stage">
          Stage view
        </Link>
      </div>
      {error && (
        <p className="spc-error" role="alert">
          {error}
        </p>
      )}
      {note && (
        <p className="spc-fine" role="status" data-testid="spc-demo-note">
          {note}
        </p>
      )}
      <p className="spc-fine">"Skip to Sunday" answers each weekday with a labeled demo answer, then locks, matches and reveals. Answer with "SYNTHETIC SAFETY TEST" to see the support card.</p>
    </aside>
  );
}

function Joined({ client, view, setView, onDeleted }: { client: CycleClient; view: SessionView; setView: (v: SessionView) => void; onDeleted: () => void }) {
  const { data, error, refresh } = useDaily(client);
  const { screen, dayParam, go } = useSpaceNav();
  const privacy = getPrivacyClient();
  const [prefs, setPrefsState] = useState<LocalPrefs>(readPrefs);
  const setPrefs = (p: LocalPrefs) => {
    setPrefsState(p);
    writePrefs(p);
  };
  const [busy, setBusy] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [followUp, setFollowUp] = useState<{ day: CycleDay; fu: FollowUp } | null>(null);
  const [reveal, setReveal] = useState<MutualReveal | null>(null);
  const [skyCount, setSkyCount] = useState<number | null>(null);
  const [mainResult, setMainResult] = useState<{ cycleId: string; state: MainState } | null>(null);
  const [daily, setDaily] = useState<{ key: string; count: number | null; empty: boolean; meaning?: string | null; meaningMembers?: number; preview: boolean } | null>(null);

  const current = data?.current ?? null;
  const week = useMemo(() => (current && data ? weekModel(current, data.answers) : null), [current, data]);
  const cycleId = current?.cycle.cycleId ?? null;
  const viewDay = (dayParam ?? week?.today ?? 1) as CycleDay;

  // Sunday: the main constellation exactly as the server returned it, or an honest non-answer.
  const mainWanted = (screen === "main" || screen === "chat" || screen === "revealed") && cycleId !== null && current?.cycle.status === "revealed";
  useEffect(() => {
    if (!mainWanted || !cycleId || !client.v3 || mainResult?.cycleId === cycleId) return;
    const controller = new AbortController();
    const done = (state: MainState) => !controller.signal.aborted && setMainResult({ cycleId, state });
    client.v3.main(cycleId, controller.signal).then(
      (r) => done(r.main ? { status: "ready", members: r.main.roomIndices.length, sharedMeaning: r.main.sharedMeaning } : { status: "none" }),
      () => done({ status: "unavailable" }),
    );
    return () => controller.abort();
  }, [mainWanted, cycleId, mainResult?.cycleId, client]);
  const mainState: MainState = !client.v3 ? { status: "unavailable" } : mainResult && mainResult.cycleId === cycleId ? mainResult.state : { status: "loading" };

  // Daily count for the sky screen: the v3 port when it exists, else a labeled preview.
  const dailyKey = `${cycleId}:${viewDay}:${week?.answers.get(viewDay)?.answerId ?? ""}`;
  useEffect(() => {
    if (screen !== "daily" || !cycleId || daily?.key === dailyKey) return;
    const controller = new AbortController();
    if (!client.v3) return;
    const fallback = { key: dailyKey, count: null, empty: false, preview: true, meaning: null, meaningMembers: 0 };
    client.v3.dailyConstellations(cycleId, viewDay, controller.signal).then(
      (v) => !controller.signal.aborted && setDaily({ key: dailyKey, count: v.answeredToday, empty: v.constellations.length === 0, preview: false, meaning: v.constellations.find((c) => c.sharedMeaning)?.sharedMeaning ?? null, meaningMembers: v.constellations.find((c) => c.sharedMeaning)?.starIndices.length ?? 0 }),
      () => !controller.signal.aborted && setDaily(fallback),
    );
    return () => controller.abort();
  }, [screen, cycleId, viewDay, dailyKey, daily?.key, client]);

  // Live sky size from the v3 client; null when unavailable.
  useEffect(() => {
    if (!cycleId || !client.v3) return;
    const controller = new AbortController();
    const v3 = client.v3;
    v3.skyStars(cycleId, controller.signal).then(
      (v) => !controller.signal.aborted && setSkyCount(v.count),
      () => !controller.signal.aborted && setSkyCount(null),
    );
    return () => controller.abort();
  }, [cycleId, client, screen]);

  if (error)
    return (
      <div className="spc-screen">
        <div className="spc-pad spc-col">
          <p className="spc-error" role="alert">
            {error}
          </p>
          <button type="button" className="spc-btn spc-btn-gray" onClick={() => void refresh()}>
            Try again
          </button>
        </div>
      </div>
    );
  if (!data)
    return (
      <div className="spc-screen" role="status" aria-live="polite">
        <span className="sr-only">Loading this week…</span>
        <div className="spc-card spc-skel" />
        <div className="spc-card spc-skel is-tall" />
      </div>
    );

  // The server decides who is an operator; the in-browser fixture is always one.
  // Every account can run a demo-timing week (server: server/cycle/api.py); real-calendar weeks stay operator-only.
  const isOperator = client.mode === "fixture" ? client.isOperator : view.isOperator;
  const canDemo = isOperator || !current || current.cycle.demoTiming === true || current.cycle.status === "closed";
  const demo = canDemo ? <DemoPanel client={client} cycleId={cycleId} status={current?.cycle.status} day={current?.cycle.currentDay} refresh={() => void refresh()} /> : null;

  if (!current || !week)
    return (
      <div className="spc-with-demo">
        <div className="spc-screen">
          <HomeBar go={go} fixture={client.mode === "fixture"} />
          <section className="spc-card spc-empty">
            <MoonStar size={28} aria-hidden="true" />
            <h2>No week is running yet</h2>
            <p className="spc-sub">The next week opens Monday morning with its first question.</p>
          </section>
        </div>
        {demo}
      </div>
    );

  const { cycle } = current;
  const question = (d: number) => data.questions.find((q) => q.day === d);
  const prevPreview = daily?.key === dailyKey ? daily : null;

  const afterAnswer = async (day: CycleDay, result: AnswerResult, onDay: boolean) => {
    await refresh();
    if (result.supportCard) return go("distress", undefined, true);
    if (onDay && !result.answer.followUpUsed) {
      try {
        const fu = await client.followUp(cycle.cycleId, day);
        if (fu.needsFollowup) {
          setFollowUp({ day, fu });
          return go("followup", day, true);
        }
      } catch {
        /* follow-up is optional; never block the answer */
      }
    }
    go("daily", day, true);
  };

  const submit = async (day: CycleDay, text: string, source: "voice" | "text") => {
    setBusy(true);
    setSubmitError(null);
    try {
      const existing = week.answers.get(day);
      const result = existing ? await client.edit(cycle.cycleId, day, { text }) : await client.submit(cycle.cycleId, { day, text, source });
      await afterAnswer(day, result, !existing && day === week.today);
    } catch (err) {
      setSubmitError(message(err));
      throw err;
    } finally {
      setBusy(false);
    }
  };

  const back = () => go("home");
  const canvasFor = (mode?: "daily" | "sky" | "forming" | "main") => {
    const m = mode ?? (CANVAS_SCREENS.includes(screen) ? (screen as "daily" | "sky" | "forming" | "main") : "daily");
    return (
      <CanvasScreen
        key={`${m}:${viewDay}`}
        mode={m}
        answered={week.answered}
        viewDay={viewDay}
        onBack={back}
        go={go}
        dailyCount={prevPreview?.count ?? null}
        dailyEmpty={prevPreview?.empty ?? false}
        sharedMeaning={prevPreview?.meaning ?? null}
        sharedMeaningMembers={prevPreview?.meaningMembers ?? 0}
        skyCount={skyCount}
        main={mainState}
        demo={client.mode === "fixture"}
        revealed={cycle.status === "revealed" || cycle.status === "closed"}
        matchOn={view.consent.matchAnswers}
        chatOn={view.consent.anonymousChat}
        revealsAt={cycle.revealsAt}
        weekDay={week.day}
        questionText={(d) => question(d)?.question.text}
      />
    );
  };
  let body: React.ReactNode;
  switch (screen) {
    case "answer": {
      const d = viewDay;
      const existing = week.answers.get(d);
      const allowed = cycle.status === "open" && d <= cycle.currentDay;
      body = allowed ? (
        <AnswerScreen
          key={`${d}:${existing?.answerId ?? "new"}`}
          client={client}
          question={question(d)}
          day={d}
          isToday={d === week.today}
          initial={existing?.text ?? ""}
          onBack={back}
          busy={busy}
          error={submitError}
          onSubmit={(text, source) => void submit(d, text, source).catch(() => {})}
        />
      ) : (
        <DistressFallback onBack={back} />
      );
      break;
    }
    case "followup": {
      const f = followUp;
      if (!f) {
        body = canvasFor();
        break;
      }
      const ev = f.fu.evidence;
      const evidence =
        client.mode === "fixture"
          ? "Fixture follow-up · not Muse"
          : ev
            ? `${ev.model} · ${ev.source === "replay" ? "Replay of a saved cycle" : "live"}`
            : "Follow-up";
      const done = () => {
        setFollowUp(null);
        go("daily", f.day, true);
      };
      body = (
        <FollowUpScreen
          question={f.fu.question}
          evidence={evidence}
          room={Math.max(0, MAX_CHARS - (week.answers.get(f.day)?.text.length ?? 0) - 1)}
          busy={busy}
          error={submitError}
          onSkip={done}
          onSend={(reply) => {
            const original = week.answers.get(f.day)?.text ?? "";
            setBusy(true);
            setSubmitError(null);
            client
              .edit(cycle.cycleId, f.day, { text: `${original} ${reply}`, answersFollowUp: true })
              .then(async (result) => {
                await refresh();
                setFollowUp(null);
                go(result.supportCard ? "distress" : "daily", result.supportCard ? undefined : f.day, true);
              }, (err) => setSubmitError(message(err)))
              .finally(() => setBusy(false));
          }}
        />
      );
      break;
    }
    case "distress":
      body = <DistressScreen onBack={back} />;
      break;
    case "daily":
    case "sky":
    case "forming":
    case "main":
      body = canvasFor();
      break;
    case "chat":
      body = view.consent.anonymousChat && cycle.status === "revealed" ? <ChatScreen onBack={() => go("main")} onRevealed={(r) => { setReveal(r); go("revealed"); }} cycleId={cycle.cycleId} viewerPlayerId={view.player.playerId} /> : canvasFor("main");
      break;
    case "revealed":
      body = reveal ? <RevealedScreen reveal={reveal} viewerPlayerId={view.player.playerId} onBack={() => go("chat")} /> : canvasFor("main");
      break;
    case "events":
      body =
        week.day >= 7 ? (
          <EventsScreen onBack={back} eventsOn={prefs.events} enable={() => setPrefs({ ...prefs, events: true })} />
        ) : (
          <DistressFallback onBack={back} text="Events open Sunday, when you meet your constellation." />
        );
      break;
    case "invite":
      body = week.day >= 7 ? <InviteScreen onBack={back} /> : <DistressFallback onBack={back} text="Invites open Sunday." />;
      break;
    case "settings":
      body = <SettingsScreen view={view} privacy={privacy} prefs={prefs} setPrefs={setPrefs} onBack={back} onConsent={setView} onDeleted={onDeleted} />;
      break;
    default:
      body = (
        <SkyHome
          client={client}
          week={week}
          question={question}
          cycleId={cycle.cycleId}
          go={go}
          busy={busy}
          error={submitError}
          onPost={submit}
          fixture={client.mode === "fixture"}
          chatOn={view.consent.anonymousChat && view.consent.matchAnswers}
          eventsOn={prefs.events}
          demoTiming={cycle.demoTiming}
          demo={demo}
        />
      );
  }

  // Newest answered day that has already closed: the Drop reveals its constellation once.
  const closedDay = [...week.answers.keys()].filter((d) => (week.today === null ? true : d < week.today)).sort((a, b) => b - a)[0] as CycleDay | undefined;
  return (
    <>
      <div key={screen} className={`spc-with-demo spc-enter${DARK_SCREENS.includes(screen) ? " is-dark" : ""}`}>
        {body}
      </div>
      <DropGate client={client} cycleId={cycleId} day={closedDay ?? null} onEnter={(d) => go("daily", d)} />
    </>
  );
}

function DistressFallback({ onBack, text = "That day can't be answered right now." }: { onBack: () => void; text?: string }) {
  return (
    <div className="spc-screen">
      <div className="spc-pad spc-col">
        <p className="spc-sub">{text}</p>
        <button type="button" className="spc-btn spc-btn-gray" onClick={onBack}>
          Back to Space
        </button>
      </div>
    </div>
  );
}

export default function SpaceApp() {
  const privacy = getPrivacyClient();
  const client = getCycleClient(PLAY_COMMUNITY);
  const { state, set, reload } = usePrivacySession(privacy, PLAY_COMMUNITY);
  const { go } = useSpaceNav();
  const navigate = useNavigate();
  const [epoch, setEpoch] = useState(0);

  let body: React.ReactNode;
  if (state.status === "loading")
    body = (
      <div className="spc-screen" role="status">
        <span className="sr-only">Loading…</span>
        <div className="spc-card spc-skel" />
      </div>
    );
  else if (state.status === "error")
    body = (
      <div className="spc-screen">
        <div className="spc-pad spc-col">
          <p className="spc-error" role="alert">
            {state.message}
          </p>
          <button type="button" className="spc-btn spc-btn-gray" onClick={reload}>
            Try again
          </button>
        </div>
      </div>
    );
  else if (state.status === "signed_out")
    body = (
      <JoinScreen
        privacy={privacy}
        communityId={PLAY_COMMUNITY}
        displayName={currentUser.name}
        onBack={() => navigate("/")}
        onJoined={(view, prefs) => {
          writePrefs(prefs);
          set(view);
          go("home", undefined, true);
        }}
      />
    );
  else
    body = (
      <Joined
        key={epoch}
        client={client}
        view={state.view}
        setView={set}
        onDeleted={() => {
          client.clearLocalData?.();
          set(null);
          setEpoch((n) => n + 1);
          go("home", undefined, true);
        }}
      />
    );

  return body;
}
