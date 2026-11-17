import { createRoot } from "react-dom/client";
import { StrictMode } from "react";
import App from "./App.tsx";
import "./index.css";
import "./styles/motion.css";
import { applyTheme, storedTheme } from "./lib/theme";

// Your colour, before the first paint (no flash of the default violet).
const savedTheme = storedTheme();
if (savedTheme) applyTheme(savedTheme);

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>
);
