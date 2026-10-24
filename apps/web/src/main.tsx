import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { App } from "./app/App";
import {
  applyAdminUiScale,
  readAdminUiScale,
} from "./features/admin/adminUiScale";
import { claimReactAriaPressableStyle } from "./reactAriaPressableStyle";
import "./styles.css";

claimReactAriaPressableStyle();
const adminRoute = window.location.pathname.startsWith("/admin");
document.documentElement.classList.toggle("admin-route", adminRoute);
document.body.classList.toggle("admin-route", adminRoute);
if (adminRoute) applyAdminUiScale(readAdminUiScale());

const root = document.getElementById("root");

if (root === null) {
  throw new Error("RepoNPC root element is missing");
}

createRoot(root).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
