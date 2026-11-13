import type { FormationDebugProps } from "./types";
import "./formation.css";

function Groups({ title, groups, highlight }: {
  title: string;
  groups: string[][];
  highlight: Set<string>;
}) {
  return (
    <section className="fd-column" aria-label={title}>
      <h3 className="fd-heading">{title}</h3>
      <ol className="fd-groups">
        {groups.map((group, i) => (
          <li key={group.join("-")} className="fd-group">
            <span className="fd-index">{i + 1}</span>
            {group.map((ref) => (
              <span key={ref} className={highlight.has(ref) ? "fd-ref fd-ref-split" : "fd-ref"}>
                {ref}
              </span>
            ))}
          </li>
        ))}
      </ol>
    </section>
  );
}

/** Operator-only: where meaning-based formation joined people keywords kept apart. */
export function FormationDebug({ data, evidence, totalMs, usedFallback }: FormationDebugProps) {
  const split = new Set(data.splitByBaseline.flat());
  return (
    <div className="fd-root">
      <header className="fd-header">
        <span className="fd-badge">Operator only</span>
        {usedFallback && <span className="fd-badge fd-badge-warn">Fallback grouping</span>}
        <span className="fd-meta">Formation {(totalMs / 1000).toFixed(1)} s</span>
      </header>
      <p className="fd-summary">
        {data.splitByBaseline.length} pairs Muse put together that the keyword baseline split.
        {" "}
        {data.agreements} of {data.museGroups.length} constellations match the baseline.
      </p>
      <div className="fd-columns">
        <Groups title="Keyword baseline" groups={data.baselineGroups} highlight={split} />
        <Groups title="Muse (by meaning)" groups={data.museGroups} highlight={split} />
      </div>
      <ul className="fd-evidence" aria-label="Muse calls">
        {evidence.map((e, i) => (
          <li key={`${e.callType}-${i}`} className="fd-chip">
            {e.callType} · {e.model} · {e.latencyMs} ms
            {e.source === "replay" && " · Replay of a saved cycle"}
          </li>
        ))}
      </ul>
    </div>
  );
}
