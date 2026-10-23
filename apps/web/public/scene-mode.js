(() => {
  "use strict";
  if (/^\/admin(?:\/|$)/.test(window.location.pathname)) return;
  const root = document.documentElement;
  const key = "reponpc.visitor.mode";
  const schemeKey = "reponpc.visitor.scheme";
  let ownerMode = root.getAttribute("data-owner-mode") || "system";
  let toggleAllowed = root.getAttribute("data-visitor-toggle") === "true";
  let defaultScheme = root.getAttribute("data-default-scheme") || "";
  let schemeChoiceAllowed =
    root.getAttribute("data-visitor-scheme-choice") === "true";
  let schemeIds = null;
  const validScheme = (value) =>
    typeof value === "string" && /^[a-z0-9_]{1,64}$/.test(value);
  let chosenScheme = null;
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

  function readSavedScheme() {
    try {
      const saved = window.localStorage.getItem(schemeKey);
      return validScheme(saved) ? saved : null;
    } catch {
      return null;
    }
  }

  function applyScheme(id) {
    chosenScheme =
      schemeChoiceAllowed && id && (!schemeIds || schemeIds.includes(id))
        ? id
        : null;
    // The owner's default also gets its fallback block before first paint.
    const painted =
      chosenScheme || (validScheme(defaultScheme) && defaultScheme);
    if (painted) {
      root.setAttribute("data-visitor-scheme", painted);
    } else {
      root.removeAttribute("data-visitor-scheme");
    }
  }

  const effectiveScheme = () => chosenScheme || defaultScheme;

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
  applyScheme(schemeChoiceAllowed ? readSavedScheme() : null);

  window.RepoNPCSceneMode = Object.freeze({
    get: effectiveMode,
    getScheme: effectiveScheme,
    setScheme(id) {
      if (
        !schemeChoiceAllowed ||
        (id !== null && (!validScheme(id) || !schemeIds?.includes(id)))
      ) {
        return false;
      }
      const selected = id === defaultScheme ? null : id;
      try {
        if (selected === null) window.localStorage.removeItem(schemeKey);
        else window.localStorage.setItem(schemeKey, selected);
      } catch {
        // Appearance remains usable when storage is unavailable.
      }
      applyScheme(selected);
      window.dispatchEvent(
        new CustomEvent("reponpc:visitor-scheme-change", {
          detail: effectiveScheme(),
        }),
      );
      return true;
    },
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
    configure(
      nextOwnerMode,
      nextToggleAllowed,
      nextDefaultScheme,
      nextSchemeChoiceAllowed,
      nextSchemeIds,
    ) {
      if (!validOwnerMode(nextOwnerMode)) return effectiveMode();
      ownerMode = nextOwnerMode;
      toggleAllowed = nextToggleAllowed === true;
      root.setAttribute("data-owner-mode", ownerMode);
      root.setAttribute("data-visitor-toggle", String(toggleAllowed));
      if (
        validScheme(nextDefaultScheme) &&
        Array.isArray(nextSchemeIds) &&
        nextSchemeIds.every(validScheme) &&
        nextSchemeIds.includes(nextDefaultScheme)
      ) {
        defaultScheme = nextDefaultScheme;
        schemeChoiceAllowed = nextSchemeChoiceAllowed === true;
        schemeIds = nextSchemeIds.slice();
        root.setAttribute("data-default-scheme", defaultScheme);
        root.setAttribute(
          "data-visitor-scheme-choice",
          String(schemeChoiceAllowed),
        );
        // Retain ignored storage so a later owner policy can re-enable it.
        applyScheme(schemeChoiceAllowed ? readSavedScheme() : null);
        window.dispatchEvent(
          new CustomEvent("reponpc:visitor-scheme-change", {
            detail: effectiveScheme(),
          }),
        );
      }
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
