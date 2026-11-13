// TEST ONLY. The Playwright suite intercepts /test-api; no fixture adapter ships in the app.
import { createRoot } from "react-dom/client";
import { useState } from "react";
import { LiveConstellation } from "../LiveConstellation";
import "./preview.css";

export function HttpPreview() {
  const [cycleId, setCycleId] = useState("cycle-demo-w1");
  return (
    <main className="cst-preview">
      <p className="cst-notice">
        TEST ONLY | Synthetic player HTTP fixtures | No real session, backend or
        model call.
      </p>
      <button onClick={() => setCycleId("cycle-next")}>
        Switch test cycle
      </button>
      <LiveConstellation
        cycleId={cycleId}
        viewerPlayerId="synthetic-a"
        baseUrl="/test-api"
      />
    </main>
  );
}
createRoot(document.getElementById("root")!).render(<HttpPreview />);
