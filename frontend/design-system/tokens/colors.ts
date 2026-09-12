/**
 * Semantic color tokens.
 *
 * Colors are named semantically, not by value (not "blue500" or "gray100").
 * This indirection allows the entire app to be restyled centrally.
 *
 * `colors` below covers UI chrome that should NOT vary per tenant — surfaces,
 * text, borders, and status colors (success/warning/error/info) all carry
 * fixed meaning (e.g. red = destructive) regardless of which school is using
 * the portal, so they stay static.
 *
 * `primary` / `secondary`, by contrast, ARE the tenant's brand — each school
 * sets its own colors on `TenantBranding.primary_color` / `secondary_color`.
 * `buildPaletteConfig()` below turns those into a full MUI palette, with a
 * safe fallback when a tenant hasn't set one and automatic light/dark
 * shades + contrast-safe text so an arbitrary admin-picked color never
 * produces unreadable buttons.
 */

export const colors = {
  // Background surfaces (Canvas, Surface, Elevated)
  background: {
    default: '#f9fafb',    // app canvas
    surface: '#ffffff',    // main content surfaces (cards, panels)
    elevated: '#fafbfc',   // dialogs, menus, floating elements (subtle lift)
  },

  // Text colors with semantic meaning
  text: {
    primary: '#111827',    // primary content, high contrast
    secondary: '#6b7280',  // secondary content
    muted: '#9ca3af',      // hints, helper text, disabled labels
    disabled: '#d1d5db',   // disabled text
    inverse: '#ffffff',    // text on dark backgrounds
  },

  // Borders
  border: {
    default: '#e5e7eb',    // standard borders, dividers
    light: '#f3f4f6',      // subtle dividers
  },

  // Semantic status colors — fixed meaning, never tenant-branded
  status: {
    success: '#10b981',       // success, valid, positive actions
    successLight: '#d1fae5',  // success background, badges

    warning: '#f59e0b',       // warning, caution
    warningLight: '#fef3c7',  // warning background, badges

    error: '#ef4444',         // error, destructive, invalid
    errorLight: '#fee2e2',    // error background, badges

    info: '#0ea5e9',          // informational
    infoLight: '#cffafe',     // info background, badges

    pending: '#8b5cf6',       // pending, in-progress
    pendingLight: '#ede9fe',  // pending background, badges
  },

  // Neutral grays (used sparingly, prefer semantic colors above)
  gray: {
    '50': '#f9fafb',
    '100': '#f3f4f6',
    '200': '#e5e7eb',
    '300': '#d1d5db',
    '400': '#9ca3af',
    '500': '#6b7280',
    '600': '#4b5563',
    '700': '#374151',
    '800': '#1f2937',
    '900': '#111827',
  },

  // Default brand — used only until a tenant's own colors are known
  // (first paint, loading states, or a tenant that hasn't set one yet).
  defaultBrand: {
    primary: '#3b82f6',
    secondary: '#7c3aed', // was accidentally aliased to `status.info` before —
                            // secondary now has its own distinct hue.
  },
};

// ---------------------------------------------------------------------------
// Tenant-color helpers
// ---------------------------------------------------------------------------

const HEX_RE = /^#([0-9a-f]{3}|[0-9a-f]{6})$/i;

/** Expand `#abc` to `#aabbcc`; returns null if not a valid hex color. */
export function normalizeHex(input: string | undefined | null): string | null {
  if (!input) return null;
  const value = input.trim();
  if (!HEX_RE.test(value)) return null;
  if (value.length === 4) {
    const [, r, g, b] = value;
    return `#${r}${r}${g}${g}${b}${b}`.toLowerCase();
  }
  return value.toLowerCase();
}

function hexToRgb(hex: string) {
  const int = parseInt(hex.slice(1), 16);
  return { r: (int >> 16) & 255, g: (int >> 8) & 255, b: int & 255 };
}

function rgbToHex(r: number, g: number, b: number) {
  const clamp = (n: number) => Math.max(0, Math.min(255, Math.round(n)));
  return `#${[clamp(r), clamp(g), clamp(b)].map((n) => n.toString(16).padStart(2, '0')).join('')}`;
}

/**
 * Mix a hex color toward white (positive amount) or black (negative), 0–1.
 * Exported as `mixColor` so component-level overrides (buildTheme.ts) can
 * derive hover/active/disabled shades from the SAME math used for the
 * palette's light/dark, instead of hardcoding a separate shade per state.
 */
export function mixColor(hex: string, amount: number) {
  const { r, g, b } = hexToRgb(hex);
  const target = amount >= 0 ? 255 : 0;
  const t = Math.abs(amount);
  return rgbToHex(r + (target - r) * t, g + (target - g) * t, b + (target - b) * t);
}

/** WCAG relative luminance → pick black or white text, whichever reads better. */
export function getReadableTextColor(hex: string): string {
  const { r, g, b } = hexToRgb(hex);
  const [rl, gl, bl] = [r, g, b].map((c) => {
    const s = c / 255;
    return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
  });
  const luminance = 0.2126 * rl + 0.7152 * gl + 0.0722 * bl;
  return luminance > 0.5 ? colors.text.primary : colors.text.inverse;
}

export interface TenantColorInput {
  primary_color?: string;
  secondary_color?: string;
}

/**
 * Build an MUI palette rooted in a specific school's brand colors.
 * Falls back to the app default brand for any color the tenant hasn't set
 * or that isn't a valid hex string (never trust admin-entered color input
 * blindly — a bad value here would otherwise silently break every button).
 */
export function buildPaletteConfig(tenant?: TenantColorInput) {
  const primaryMain = normalizeHex(tenant?.primary_color) ?? colors.defaultBrand.primary;
  const secondaryMain = normalizeHex(tenant?.secondary_color) ?? colors.defaultBrand.secondary;

  return {
    primary: {
      main: primaryMain,
      light: mixColor(primaryMain, 0.25),
      dark: mixColor(primaryMain, -0.25),
      contrastText: getReadableTextColor(primaryMain),
    },
    secondary: {
      main: secondaryMain,
      light: mixColor(secondaryMain, 0.25),
      dark: mixColor(secondaryMain, -0.25),
      contrastText: getReadableTextColor(secondaryMain),
    },
    success: {
      main: colors.status.success,
      light: colors.status.successLight,
      contrastText: colors.text.inverse,
    },
    warning: {
      main: colors.status.warning,
      light: colors.status.warningLight,
      contrastText: '#111827',
    },
    error: {
      main: colors.status.error,
      light: colors.status.errorLight,
      contrastText: colors.text.inverse,
    },
    info: {
      main: colors.status.info,
      light: colors.status.infoLight,
      contrastText: colors.text.inverse,
    },
    background: {
      default: colors.background.default,
      paper: colors.background.surface,
    },
    text: {
      primary: colors.text.primary,
      secondary: colors.text.secondary,
      disabled: colors.text.disabled,
    },
    divider: colors.border.default,
    action: {
      active: primaryMain,
      // NOTE: these are consumed by MUI as plain hex, so precise 8-digit
      // alpha-hex is used directly rather than the old string-concatenation
      // approach (`${hex}08`), which silently breaks if `primaryMain` isn't
      // exactly 6 hex digits — now guaranteed by normalizeHex() above.
      hover: `${primaryMain}0d`,      // ~5%
      selected: `${primaryMain}1f`,   // ~12%
      disabledBackground: `${primaryMain}40`, // ~25%
      focus: `${primaryMain}33`,      // ~20%
    },
  };
}

/** Default palette for first paint / before tenant data has loaded. */
export const paletteConfig = buildPaletteConfig();