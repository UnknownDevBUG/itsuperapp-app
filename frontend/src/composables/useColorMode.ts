import { ref } from "vue";

// Minimal color-mode state for the frontend shell (ADR 0006's first round is
// Login + Layout only). Replace with a persisted/system-preference-aware
// implementation when a real theme-switcher lands; kept intentionally small
// so JastelLogo has something concrete to react to today.
const mode = ref<"light" | "dark">("light");

export function useColorMode() {
  return { mode };
}
