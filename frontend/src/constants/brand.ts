// Fixed JasTel brand-identity colors for the logo mark — these must stay
// constant regardless of app theme, ported verbatim from document-ai's
// src/lib/constants.ts (JASTEL_BRAND_COLORS) per ADR 0006.
export const JASTEL_BRAND_COLORS = {
  GLOBE_GRADIENT_START: "#60A5FA",
  GLOBE_GRADIENT_END: "#1E40AF",
  ORBIT_RING: "#94A3B8",
  LANDMASS_GREEN: "#4ADE80",
  ATMOSPHERE_HIGHLIGHT: "#F1F5F9",
  SATELLITE_ORANGE: "#F97316",
  SATELLITE_CORE: "#FFFFFF",
  WORDMARK_JAS: "#F97316",
  WORDMARK_TEL_DARK: "#38BDF8",
  WORDMARK_TEL_LIGHT: "#0369A1",
  TAGLINE_DARK: "#94A3B8",
  TAGLINE_LIGHT: "#64748B",
} as const;
