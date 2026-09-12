import { createRoot } from "react-dom/client";
import { App } from "./src/app/App";
import "./src/styles.css";

// In-memory public API fixture: no request reaches a server or model.
window.fetch = async (input) => {
  const path = String(input);
  const response =
    path === "/api/public/status"
      ? { chat_available: true }
      : path.startsWith("/api/public/profile?")
        ? {
            profile: {
              display_name: "Synthetic portfolio",
              headline: "A layout test",
              greeting: "Welcome",
              bio: "Long unbroken fields must wrap.",
              location: null,
              avatar_url: null,
              links: [],
            },
            repositories: [
              {
                slug: "example/" + "long-project-".repeat(12),
                summary: "x".repeat(150),
                role: "Synthetic maintainer",
                tags: ["long-tag-".repeat(12)],
                demo_url: null,
              },
            ],
            suggested_questions: ["Explain this synthetic project"],
            character: {
              mode: "builtin",
              asset_url: "",
              revision: 1,
              frame_duration_ms: 160,
              movement: "none",
            },
          }
        : { error: { code: "FIXTURE_UNHANDLED" } };
  return new Response(JSON.stringify(response), {
    status: path.includes("/chat/") ? 503 : 200,
    headers: { "Content-Type": "application/json" },
  });
};
createRoot(document.getElementById("root")!).render(<App />);
