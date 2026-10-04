import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import "./index.css";
import "./styles/docs.css";
import { AppRouter } from "./AppRouter";
import { initTheme } from "./lib/theme";

// Before the first render, so the page never flashes the wrong theme.
initTheme();

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <AppRouter />
  </StrictMode>,
);
