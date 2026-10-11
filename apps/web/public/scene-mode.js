(() => {
  "use strict";
  if (/^\/admin(?:\/|$)/.test(window.location.pathname)) return;
  const root = document.documentElement;
  const key = "reponpc.visitor.mode";
  let ownerMode = root.getAttribute("data-owner-mode") || "system";
  let toggleAllowed = root.getAttribute("data-visitor-toggle") === "true";
  const validMode = (value) => value === "light" || value === "dark";
  const validOwnerMode = (value) => ["system", "light", "dark"].includes(value);

  function readSavedMode() {
    try {
      const saved = window.localStorage.getItem(key);
      return validMode(saved) ? saved : null;
    } catch {
      return null;
    }
  }

  function applyMode(mode) {
    if (mode === "light" || mode === "dark") {
      root.setAttribute("data-visitor-mode", mode);
    } else {
      root.removeAttribute("data-visitor-mode");
    }
  }

  function effectiveMode() {
    if (!toggleAllowed) return ownerMode;
    const saved = readSavedMode();
    if (saved) return saved;
    const selected = root.getAttribute("data-visitor-mode");
    if (validMode(selected) && selected !== ownerMode) return selected;
    return ownerMode;
  }

  const initialMode = toggleAllowed ? readSavedMode() || ownerMode : ownerMode;
  applyMode(initialMode);

  window.RepoNPCSceneMode = Object.freeze({
    get: effectiveMode,
    set(mode) {
      if (
        root.getAttribute("data-visitor-toggle") !== "true" ||
        !["system", "light", "dark"].includes(mode)
      ) {
        return false;
      }
      try {
        if (mode === "system") window.localStorage.removeItem(key);
        else window.localStorage.setItem(key, mode);
      } catch {
        // Appearance remains usable when storage is unavailable.
      }
      applyMode(mode === "system" ? ownerMode : mode);
      window.dispatchEvent(
        new CustomEvent("reponpc:visitor-mode-change", {
          detail: effectiveMode(),
        }),
      );
      return true;
    },
    configure(nextOwnerMode, nextToggleAllowed) {
      if (!validOwnerMode(nextOwnerMode)) return effectiveMode();
      ownerMode = nextOwnerMode;
      toggleAllowed = nextToggleAllowed === true;
      root.setAttribute("data-owner-mode", ownerMode);
      root.setAttribute("data-visitor-toggle", String(toggleAllowed));
      const saved = toggleAllowed ? readSavedMode() : null;
      applyMode(saved || ownerMode);
      const selected = effectiveMode();
      window.dispatchEvent(
        new CustomEvent("reponpc:visitor-mode-change", { detail: selected }),
      );
      return selected;
    },
  });
})();
