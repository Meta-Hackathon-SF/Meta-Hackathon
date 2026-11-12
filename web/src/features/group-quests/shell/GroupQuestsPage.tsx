import { useMemo, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router";
import type { Consent, Id, PrivateIntent } from "../../../../../contracts/protocol";
import IntentOnboarding from "../onboarding/IntentOnboarding";
import { createFixtureOnboardingPorts } from "../onboarding/fixtureAdapter";
import { createHttpOnboardingPorts } from "../onboarding/httpAdapter";
import type { OnboardingCommunity, OnboardingPorts } from "../onboarding/types";
import { findCommunity } from "./communities";
import { featureSlots, type GroupQuestsSlots } from "./slots";
import { formatElapsed, useFirstActionTimer } from "./useFirstActionTimer";
import "./shell.css";
import "../onboarding/onboarding.css";

/** Public setting only. Never put provider or database keys in VITE_ vars. */
const API_BASE = import.meta.env.VITE_GQ_API_BASE as string | undefined;

function usePorts(community: OnboardingCommunity | null): OnboardingPorts | null {
  const [params] = useSearchParams();
  const delay = params.get("gqFixtureDelay");
  const fail = params.get("gqFixtureFail");
  return useMemo(() => {
    if (!community) return null;
    // TODO(P2): take mode from the server session instead of assuming live.
    if (API_BASE) return createHttpOnboardingPorts(API_BASE, "live");
    return createFixtureOnboardingPorts({
      community,
      delayMs: delay !== null && /^\d{1,5}$/.test(delay) ? Number(delay) : undefined,
      fail: fail === "transcribe" || fail === "extract" || fail === "confirm" ? fail : null,
    });
  }, [community, delay, fail]);
}

function Pending({ owner, what }: { owner: string; what: string }) {
  return (
    <p className="gq-slot-empty">
      <span className="gq-badge gq-badge-muted">Not integrated</span> {what} ({owner}'s component) will appear here.
    </p>
  );
}

export default function GroupQuestsPage({ slots = featureSlots }: { slots?: GroupQuestsSlots }) {
  const { communityId } = useParams();
  const community = findCommunity(communityId);
  const ports = usePorts(community);
  const [consent, setConsent] = useState<Consent | null>(null);
  const [fixtureConsent, setFixtureConsent] = useState(false);
  const [intent, setIntent] = useState<PrivateIntent | null>(null);
  const [questId, setQuestId] = useState<Id | null>(null);
  const timer = useFirstActionTimer();

  if (!community || !ports) {
    return (
      <main className="gq-root" id="main-content">
        <div className="gq-card">
          <h1 className="gq-title">Community not found</h1>
          <p className="gq-muted">Group Quests isn't available for this community.</p>
          <Link className="gq-button gq-button-secondary" to="/groups">
            Back to Groups
          </Link>
        </div>
      </main>
    );
  }

  const mode = ports.mode;
  const consentGranted = slots.privacy
    ? !!consent && consent.matching && consent.modelProcessing && consent.revokedAt === null
    : mode === "fixture" && fixtureConsent;
  const Privacy = slots.privacy;
  const Matching = slots.matching;
  const Planning = slots.planning;
  const Events = slots.events;

  return (
    <main className="gq-root" id="main-content" aria-labelledby="gq-page-title">
      <header className="gq-hero">
        <div>
          <p className="gq-eyebrow">
            <Link to="/groups">Groups</Link> / {community.name}
          </p>
          <h1 id="gq-page-title" className="gq-title">
            Group Quests
          </h1>
          <p className="gq-subtitle">Turn a shared interest into a small plan with 3–5 people from this community.</p>
        </div>
        <ul className="gq-badges" aria-label="Demo labels">
          <li className="gq-badge">Facebook integration simulated</li>
          {mode === "fixture" && (
            <li className="gq-badge gq-badge-warn" data-testid="gq-mode">
              Fixture mode · no Muse calls
            </li>
          )}
          {mode === "replay" && <li className="gq-badge gq-badge-warn">Replay</li>}
          {mode === "live" && <li className="gq-badge gq-badge-live">Live</li>}
        </ul>
      </header>

      <div className="gq-layout">
        <div className="gq-main">
          <section className="gq-step" aria-labelledby="gq-step-join">
            <h2 id="gq-step-join" className="gq-step-title">
              <span className="gq-step-number">1</span> Join Group Quests
            </h2>
            {Privacy ? (
              <Privacy communityId={community.communityId} mode={mode} onConsentChange={setConsent} />
            ) : mode === "fixture" ? (
              <div className="gq-card gq-card-compact">
                <label className="gq-check">
                  <input
                    type="checkbox"
                    checked={fixtureConsent}
                    onChange={(event) => setFixtureConsent(event.target.checked)}
                  />
                  <span>
                    <strong>Fixture consent:</strong> let this development build process my intent for matching.
                  </span>
                </label>
                <p className="gq-muted gq-small">
                  Stand-in until Patrik's consent component lands. Nothing leaves this browser in fixture mode.
                </p>
              </div>
            ) : (
              <Pending owner="Patrik" what="Sign-in and consent" />
            )}
          </section>

          <section className="gq-step" aria-labelledby="gq-step-intent">
            <h2 id="gq-step-intent" className="gq-step-title">
              <span className="gq-step-number">2</span> Your intent
            </h2>
            <IntentOnboarding
              community={community}
              ports={ports}
              consentGranted={consentGranted}
              onConfirmed={(confirmed) => {
                setIntent(confirmed);
                setQuestId(null);
                timer.start(confirmed.intentVersion);
              }}
              onEditStarted={() => timer.abandon("intent_edited")}
            />
          </section>

          <section className="gq-step" aria-labelledby="gq-step-team">
            <h2 id="gq-step-team" className="gq-step-title">
              <span className="gq-step-number">3</span> Your team
            </h2>
            {!intent ? (
              <p className="gq-slot-empty">Confirm your intent to look for a team.</p>
            ) : Matching ? (
              <Matching
                communityId={community.communityId}
                mode={mode}
                confirmedIntentVersion={intent.intentVersion}
                onQuestCreated={setQuestId}
              />
            ) : (
              <Pending owner="Rishi" what="Team matching" />
            )}
          </section>

          <section className="gq-step" aria-labelledby="gq-step-plan">
            <h2 id="gq-step-plan" className="gq-step-title">
              <span className="gq-step-number">4</span> Plan and event
            </h2>
            {!questId ? (
              <p className="gq-slot-empty">Your plan appears once a team forms.</p>
            ) : (
              <>
                {Planning ? (
                  <Planning communityId={community.communityId} mode={mode} questId={questId} />
                ) : (
                  <Pending owner="Adam" what="The activity plan" />
                )}
                {Events ? (
                  <Events
                    communityId={community.communityId}
                    mode={mode}
                    questId={questId}
                    onAccepted={timer.complete}
                  />
                ) : (
                  <Pending owner="Kai" what="Acceptance and the event" />
                )}
              </>
            )}
          </section>
        </div>

        <aside className="gq-aside" aria-label="First action timer">
          <div className="gq-card gq-card-compact">
            <h2 className="gq-aside-title">Time to first action</h2>
            <p className="gq-timer" data-testid="gq-timer" aria-live="off">
              {formatElapsed(timer.elapsedMs)}
            </p>
            <p className="gq-muted gq-small" data-testid="gq-timer-status">
              {!timer.current
                ? "Starts when your intent is confirmed."
                : timer.current.outcome === "running"
                  ? Events
                    ? "Running. Stops when your quest acceptance is saved."
                    : "Running. Can't stop yet: the acceptance step isn't integrated."
                  : timer.current.outcome === "completed"
                    ? "Measured: confirmed intent to saved acceptance."
                    : "Stopped: you edited your intent. It restarts when you confirm again."}
            </p>
            {timer.attempts.length > 1 && (
              <p className="gq-muted gq-small">
                Attempts: {timer.attempts.filter((a) => a.outcome === "completed").length} completed,{" "}
                {timer.attempts.filter((a) => a.outcome === "abandoned").length} abandoned
              </p>
            )}
          </div>
        </aside>
      </div>
    </main>
  );
}
