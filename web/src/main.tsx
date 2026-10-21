import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { KeyNotationProvider } from "./hooks/useKeyNotation";
import "./styles/tokens.css";
import "./styles/globals.css";
import "./styles/review.css";
import "./styles/config.css";
import "./styles/library.css";
import "./styles/model.css";
import App from "./App";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <KeyNotationProvider>
      <App />
    </KeyNotationProvider>
  </StrictMode>
);
