/**
 * Shadow / elevation scale tokens.
 *
 * Three elevation levels for clear visual hierarchy.
 * Never changed per tenant.
 */

export const shadows = {
  none: 'none',

  // Subtle shadow: for hover states, subtle depth
  subtle: '0px 1px 2px rgba(0, 0, 0, 0.05)',

  // Floating shadow: for dialogs, menus, floating elements
  floating: '0px 10px 25px rgba(0, 0, 0, 0.1)',
};

/**
 * MUI elevation levels (0-24).
 * Maps our semantic shadows to MUI's elevation system.
 */
export const muiElevations = {
  // Level 0: no elevation
  0: shadows.none,

  // Level 1-2: subtle elevation (hover states)
  1: shadows.subtle,
  2: shadows.subtle,

  // Level 3-24: floating elevation (cards, dialogs, menus)
  3: shadows.floating,
  4: shadows.floating,
  5: shadows.floating,
  6: shadows.floating,
  7: shadows.floating,
  8: shadows.floating,
  9: shadows.floating,
  10: shadows.floating,
  11: shadows.floating,
  12: shadows.floating,
  13: shadows.floating,
  14: shadows.floating,
  15: shadows.floating,
  16: shadows.floating,
  17: shadows.floating,
  18: shadows.floating,
  19: shadows.floating,
  20: shadows.floating,
  21: shadows.floating,
  22: shadows.floating,
  23: shadows.floating,
  24: shadows.floating,
};
