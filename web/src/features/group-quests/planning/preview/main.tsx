// Dev-only fixture preview for planning components. Not part of the production
// bundle (only web/index.html is a build entry). Served by `npm run dev` at
// /src/features/group-quests/planning/preview/index.html
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "../../../../index.css";
import Preview from "./Preview";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <Preview />
  </StrictMode>,
);
