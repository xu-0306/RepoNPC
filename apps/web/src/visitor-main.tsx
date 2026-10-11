import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { VisitorApp } from "./app/VisitorApp";

const root = document.getElementById("root");
if (root === null) throw new Error("RepoNPC visitor root is missing");

createRoot(root).render(
  <StrictMode>
    <VisitorApp />
  </StrictMode>,
);
