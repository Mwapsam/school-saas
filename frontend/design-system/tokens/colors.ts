/**
 * Semantic color tokens.
 *
 * Colors are named semantically, not by value (not "blue500" or "gray100").
 * This indirection allows the entire app to be restyled centrally.
 */

export const colors = {
  // Background surfaces (Canvas, Surface, Elevated)
  background: {
    default: '#f9fafb',    // app canvas
    surface: '#ffffff',    // main content surfaces
    elevated: '#ffffff',   // dialogs, menus, floating elements
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

  // Action colors (buttons, links)
  action: {
    primary: '#3b82f6',           // primary action button background
    primaryHover: '#2563eb',      // primary button hover
    primaryActive: '#1d4ed8',     // primary button active/pressed
    primaryFocus: '#3b82f6',       // primary button focus ring color
    primaryDisabled: '#bfdbfe',    // primary button disabled state

    secondary: '#e5e7eb',          // secondary action button background
    secondaryHover: '#d1d5db',     // secondary button hover
    secondaryActive: '#b3b6be',    // secondary button active
    secondaryDisabled: '#f3f4f6',  // secondary button disabled
  },

  // Semantic status colors
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
};

/**
 * MUI Palette configuration derived from semantic tokens.
 * This maps our semantic tokens to MUI's palette structure.
 */
export const paletteConfig = {
  primary: {
    main: colors.action.primary,
    light: '#60a5fa',
    dark: '#1d4ed8',
    contrastText: colors.text.inverse,
  },
  secondary: {
    main: colors.status.info,
    light: '#38bdf8',
    dark: '#0284c7',
    contrastText: colors.text.inverse,
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
    active: colors.action.primary,
    hover: `${colors.action.primary}08`,      // 5% opacity
    selected: `${colors.action.primary}12`,   // 7% opacity
    disabled: colors.action.primaryDisabled,
    disabledBackground: `${colors.action.primaryDisabled}40`,
    focus: `${colors.action.primary}1f`,      // 12% opacity
  },
};
