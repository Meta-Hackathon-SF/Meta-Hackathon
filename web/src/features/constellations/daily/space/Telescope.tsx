/*
 * Telescoping entry into the sky: a lens aperture opens from a small circle to the full view while the
 * sky behind it pulls back from a tight zoom. One smooth move, no streaks or flashes. Presentation only;
 * skipped for reduced motion; carries no data.
 */
import { useEffect, useState } from "react";

const DURATION_MS = 1600;
const reduced = () =>
  typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

export default function Telescope({ onDone }: { onDone?: () => void }) {
  const [live, setLive] = useState(() => !reduced());
  useEffect(() => {
    if (!live) {
      onDone?.();
      return;
    }
    const t = window.setTimeout(() => {
      setLive(false);
      onDone?.();
    }, DURATION_MS);
    return () => window.clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- plays once per mount
  }, []);
  if (!live) return null;
  return (
    <div className="spc-telescope" aria-hidden="true" data-testid="spc-telescope">
      <div className="spc-telescope-mask" />
      <div className="spc-telescope-ring" />
      <div className="spc-telescope-ring is-inner" />
    </div>
  );
}
