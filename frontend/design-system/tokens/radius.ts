/**
 * Border radius scale tokens.
 *
 * Small, intentional radius values. Never changed per tenant.
 */

export const radius = {
  sm: 6,      // small elements: badges, small buttons, chips
  md: 10,     // standard: buttons, inputs, small cards, avatars
  lg: 14,     // larger: cards, dropdowns, popovers
  xl: 20,     // major: dialogs, large containers, major UI elements
  full: 9999, // fully rounded (for pills, circles)
};

/**
 * MUI theme shape configuration derived from our tokens.
 */
export const muiShape = {
  borderRadius: radius.md,
};
