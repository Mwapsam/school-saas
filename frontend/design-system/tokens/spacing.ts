/**
 * Spacing scale tokens (as MUI multipliers).
 *
 * Based on 4px base unit (MUI default). MUI's spacing(n) = n * 4px.
 * Values are MUI multiplier units, not pixels.
 * These are never changed per tenant.
 */

export const spacing = {
  // Atomic scale (MUI multipliers)
  xs: 1,      // 1 * 4px = 4px
  sm: 2,      // 2 * 4px = 8px
  md: 3,      // 3 * 4px = 12px
  lg: 4,      // 4 * 4px = 16px
  xl: 6,      // 6 * 4px = 24px
  '2xl': 8,   // 8 * 4px = 32px
  '3xl': 12,  // 12 * 4px = 48px
  '4xl': 16,  // 16 * 4px = 64px

  // Semantic spacing (used in components and layouts)
  page: 8,              // 8 * 4px = 32px outer page padding
  pageVertical: 8,      // 8 * 4px = 32px top/bottom page padding
  pageHorizontal: 8,    // 8 * 4px = 32px left/right page padding

  section: 6,           // 6 * 4px = 24px spacing between major sections
  sectionVertical: 6,   // 6 * 4px = 24px top/bottom spacing between sections
  sectionHorizontal: 6, // 6 * 4px = 24px left/right section spacing

  card: 5,              // 5 * 4px = 20px padding inside cards
  cardVertical: 5,      // 5 * 4px = 20px top/bottom card padding
  cardHorizontal: 5,    // 5 * 4px = 20px left/right card padding

  component: 4,         // 4 * 4px = 16px internal spacing in components
  componentVertical: 4, // 4 * 4px = 16px top/bottom component padding
  componentHorizontal: 4, // 4 * 4px = 16px left/right component padding

  element: 3,           // 3 * 4px = 12px small internal spacing
  elementVertical: 3,   // 3 * 4px = 12px top/bottom element padding
  elementHorizontal: 3, // 3 * 4px = 12px left/right element padding

  gap: 4,               // 4 * 4px = 16px gap between grid/flex items
  gapSmall: 2,          // 2 * 4px = 8px small gap
  gapLarge: 6,          // 6 * 4px = 24px large gap
};
