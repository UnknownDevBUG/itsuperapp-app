import { ref, watch } from "vue";

// Color-mode state for the frontend shell. Three modes: light / dark /
// system (follows OS preference). Persisted in localStorage so the choice
// survives reloads, and applied as `data-theme` on <html> to match
// frappe-ui's tailwind preset (`darkMode: ['selector', '[data-theme="dark"]']`).
export type ColorModePreference = "light" | "dark" | "system";

const STORAGE_KEY = "itsuperapp-color-mode";

const mediaQuery =
  typeof window !== "undefined" ? window.matchMedia("(prefers-color-scheme: dark)") : null;

function systemPrefersDark() {
  return mediaQuery?.matches ?? false;
}

function readStoredPreference(): ColorModePreference {
  if (typeof window === "undefined") return "system";
  const stored = window.localStorage.getItem(STORAGE_KEY);
  if (stored === "light" || stored === "dark" || stored === "system") return stored;
  return "system";
}

// `preference` is the user's explicit choice (persisted); `mode` is the
// resolved light/dark value actually applied to the DOM (equals
// `preference` unless preference is "system", in which case it tracks the
// OS setting).
const preference = ref<ColorModePreference>(readStoredPreference());
const mode = ref<"light" | "dark">(preference.value === "system" ? (systemPrefersDark() ? "dark" : "light") : preference.value);

function applyToDocument() {
  if (typeof document === "undefined") return;
  document.documentElement.setAttribute("data-theme", mode.value);
}

function resolveMode() {
  mode.value = preference.value === "system" ? (systemPrefersDark() ? "dark" : "light") : preference.value;
}

watch(preference, () => {
  resolveMode();
  if (typeof window !== "undefined") {
    window.localStorage.setItem(STORAGE_KEY, preference.value);
  }
});

watch(mode, applyToDocument, { immediate: true });

mediaQuery?.addEventListener("change", () => {
  if (preference.value === "system") resolveMode();
});

export function useColorMode() {
  function setPreference(next: ColorModePreference) {
    preference.value = next;
  }

  function cyclePreference() {
    const order: ColorModePreference[] = ["light", "dark", "system"];
    const next = order[(order.indexOf(preference.value) + 1) % order.length];
    setPreference(next);
  }

  return { mode, preference, setPreference, cyclePreference };
}
