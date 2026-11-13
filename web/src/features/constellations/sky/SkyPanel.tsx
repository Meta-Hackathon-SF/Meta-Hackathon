import type { SkyStats } from "../../../../../contracts/protocol";
import { EvidenceChip } from "../chat/EvidenceChip";
import { parseSky } from "./runtime";
import "../chat/chat.css";
import "./sky.css";

export function SkyPanel({
  sky: input,
  fixture = false,
  projector = false,
}: {
  sky: SkyStats;
  fixture?: boolean;
  projector?: boolean;
}) {
  const sky = parseSky(input);
  const themes = sky.themes.filter((theme) => theme.count >= sky.threshold);
  // A malformed low-count theme may also be named in a headline. Hide all headlines
  // in that case; never infer or recompute the producer's aggregate numbers.
  const headlinesSafe = themes.length === sky.themes.length;
  const evidence = sky.evidence.find((e) => e.callType === "M8");
  return (
    <section
      className={`cst-sky ${projector ? "cst-sky-projector" : ""}`}
      aria-label="Community Sky"
    >
      <p className="cst-eyebrow">The community Sky</p>
      <h2>More in common than you thought.</h2>
      <p className="cst-muted">
        What your Group guessed. What the week showed. Only shared patterns,
        never anyone's answers.
      </p>
      {fixture && (
        <p className="cst-notice">
          Synthetic player | Synthetic signal | Synthetic fixture. Example
          numbers; no live model call.
        </p>
      )}
      <div className="cst-sky-metrics">
        <div>
          <strong>{sky.constellations}</strong>
          <span>constellations</span>
        </div>
        <div>
          <strong>{sky.eligiblePlayers}</strong>
          <span>{fixture ? "synthetic players" : "eligible players"}</span>
        </div>
        <div>
          <strong>{sky.mutualReveals}</strong>
          <span>mutual reveals</span>
        </div>
      </div>
      <div className="cst-sky-legend">
        <span>
          <i className="cst-actual-dot" /> Actual
        </span>
        <span>
          <i className="cst-guessed-dot" /> Guessed
        </span>
      </div>
      <ul className="cst-themes">
        {themes.map((theme) => (
          <li key={theme.themeId}>
            <h3>{theme.label}</h3>
            <p className="cst-theme-count">
              {theme.count} people | {sky.threshold}+ required to show a theme
            </p>
            <div className="cst-bar-row">
              <span>Actual</span>
              <div className="cst-bar-track">
                <div
                  className="cst-actual-bar"
                  style={{ width: `${theme.actualPercent}%` }}
                />
              </div>
              <strong>{theme.actualPercent}%</strong>
            </div>
            <div className="cst-bar-row">
              <span>Guessed</span>
              <div className="cst-bar-track">
                <div
                  className="cst-guessed-bar"
                  style={{ width: `${theme.guessedPercentMedian}%` }}
                />
              </div>
              <strong>{theme.guessedPercentMedian}%</strong>
            </div>
          </li>
        ))}
      </ul>
      {themes.length === 0 && (
        <p className="cst-muted">No themes meet the privacy threshold yet.</p>
      )}
      {(sky.suppressedThemes > 0 || !headlinesSafe) && (
        <p className="cst-muted">
          Some patterns stay hidden to protect privacy.
        </p>
      )}
      {headlinesSafe && (fixture || evidence) && sky.headlines.length > 0 && (
        <aside className="cst-sky-headlines">
          {sky.headlines.map((line) => (
            <p key={line}>{line}</p>
          ))}
          <EvidenceChip evidence={evidence} fixture={fixture} />
        </aside>
      )}
      {sky.syntheticSignals.length > 0 && (
        <aside className="cst-signals" aria-label="Synthetic signals">
          <h3>Synthetic signals</h3>
          <p>
            Illustrative aggregate data, separate from this Group's results.
          </p>
          {sky.syntheticSignals.map((signal) => (
            <div key={signal.signalId}>
              <span className="cst-signal-label">Synthetic signal</span>
              <p>{signal.label}</p>
              <strong>{signal.percent}%</strong>
              <small> | Synthetic sample: {signal.sampleSize}</small>
            </div>
          ))}
        </aside>
      )}
    </section>
  );
}
