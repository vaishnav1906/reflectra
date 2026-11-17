import { createRoot } from "react-dom/client";
import { StrictMode } from "react";
import App from "./App.tsx";
import "./index.css";
import "./styles/motion.css";
import "./styles/pwa.css";
import { applyTheme, storedTheme } from "./lib/theme";
import { registerServiceWorker, setupInstall } from "./lib/install";

// Your colour, before the first paint (no flash of the default violet).
const savedTheme = storedTheme();
if (savedTheme) applyTheme(savedTheme);

// Installable app: catch the install prompt early, and open offline once loaded.
setupInstall();
registerServiceWorker();

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>
);
