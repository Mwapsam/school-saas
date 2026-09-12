/**
 * Shadow / elevation scale tokens.
 *
 * Three elevation levels for clear visual hierarchy.
 * Never changed per tenant.
 */

export const shadows = {
  none: 'none',

  // Subtle shadow: for minimal depth cues
  subtle: '0px 1px 2px rgba(0, 0, 0, 0.05)',

  // Raised shadow: for hover states, interactive surfaces, cards on hover (intermediate step)
  raised: '0px 3px 8px rgba(0, 0, 0, 0.07)',

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

  // Level 1-3: subtle elevation
  1: shadows.subtle,
  2: shadows.subtle,
  3: shadows.subtle,

  // Level 4-8: raised elevation (hover states, interactive surfaces)
  4: shadows.raised,
  5: shadows.raised,
  6: shadows.raised,
  7: shadows.raised,
  8: shadows.raised,

  // Level 9-24: floating elevation (cards, dialogs, menus)
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
