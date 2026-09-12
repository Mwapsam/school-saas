/**
 * Typography scale and font configuration.
 *
 * Fixed by the platform. Tenants can only swap the typeface (e.g., Inter → Roboto),
 * but sizes, line heights, and weights never change per tenant.
 */

export const fontFamily = {
  // Primary font (self-hosted via next/font)
  primary: '"Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", "Roboto", "Helvetica Neue", Arial, sans-serif',

  // Fallback fonts for other curated choices (if tenant swaps font)
  roboto: '"Roboto", -apple-system, BlinkMacSystemFont, "Segoe UI", "Helvetica Neue", Arial, sans-serif',
  poppins: '"Poppins", -apple-system, BlinkMacSystemFont, "Segoe UI", "Roboto", "Helvetica Neue", Arial, sans-serif',
  system: '-apple-system, BlinkMacSystemFont, "Segoe UI", "Roboto", "Helvetica Neue", Arial, sans-serif',
};

/**
 * Typography scale. Fixed values, never adjusted per tenant.
 */
export const typography = {
  display: {
    fontSize: 32,
    lineHeight: 40,
    fontWeight: 700,
    letterSpacing: -0.5,
  },

  h1: {
    fontSize: { xs: '1.75rem', sm: '2rem', md: '1.75rem' },
    lineHeight: 1.2,
    fontWeight: 700,
    letterSpacing: -0.5,
  },

  h2: {
    fontSize: { xs: '1.5rem', sm: '1.75rem', md: '1.5rem' },
    lineHeight: 1.33,
    fontWeight: 650,
    letterSpacing: -0.3,
  },

  h3: {
    fontSize: { xs: '1.25rem', sm: '1.5rem', md: '1.25rem' },
    lineHeight: 1.4,
    fontWeight: 650,
    letterSpacing: -0.2,
  },

  body: {
    fontSize: 15,
    lineHeight: 24,
    fontWeight: 400,
    letterSpacing: 0,
  },

  bodySmall: {
    fontSize: 14,
    lineHeight: 20,
    fontWeight: 400,
    letterSpacing: 0,
  },

  caption: {
    fontSize: 12,
    lineHeight: 18,
    fontWeight: 500,
    letterSpacing: 0,
  },
};

/**
 * MUI Typography variants derived from our scale.
 * Used in theme.typography configuration.
 * Note: h1, h2, h3 have responsive fontSize objects, not simple numbers.
 */
export const muiTypographyVariants = {
  h1: {
    fontSize: '2rem',
    lineHeight: 1.2,
    fontWeight: typography.h1.fontWeight,
    letterSpacing: typography.h1.letterSpacing,
  },
  h2: {
    fontSize: '1.75rem',
    lineHeight: 1.33,
    fontWeight: typography.h2.fontWeight,
    letterSpacing: typography.h2.letterSpacing,
  },
  h3: {
    fontSize: '1.5rem',
    lineHeight: 1.4,
    fontWeight: typography.h3.fontWeight,
    letterSpacing: typography.h3.letterSpacing,
  },
  h4: {
    fontSize: typography.h3.fontSize,
    lineHeight: typography.h3.lineHeight / typography.h3.fontSize,
    fontWeight: typography.h3.fontWeight,
    letterSpacing: typography.h3.letterSpacing,
  },
  h5: {
    fontSize: typography.body.fontSize,
    lineHeight: typography.body.lineHeight / typography.body.fontSize,
    fontWeight: 650,
    letterSpacing: 0,
  },
  h6: {
    fontSize: typography.bodySmall.fontSize,
    lineHeight: typography.bodySmall.lineHeight / typography.bodySmall.fontSize,
    fontWeight: 650,
    letterSpacing: 0,
  },
  body1: {
    fontSize: typography.body.fontSize,
    lineHeight: typography.body.lineHeight / typography.body.fontSize,
    fontWeight: typography.body.fontWeight,
    letterSpacing: typography.body.letterSpacing,
  },
  body2: {
    fontSize: typography.bodySmall.fontSize,
    lineHeight: typography.bodySmall.lineHeight / typography.bodySmall.fontSize,
    fontWeight: typography.bodySmall.fontWeight,
    letterSpacing: typography.bodySmall.letterSpacing,
  },
  subtitle1: {
    fontSize: typography.body.fontSize,
    lineHeight: typography.body.lineHeight / typography.body.fontSize,
    fontWeight: 600,
    letterSpacing: 0,
  },
  subtitle2: {
    fontSize: typography.bodySmall.fontSize,
    lineHeight: typography.bodySmall.lineHeight / typography.bodySmall.fontSize,
    fontWeight: 600,
    letterSpacing: 0,
  },
  caption: {
    fontSize: typography.caption.fontSize,
    lineHeight: typography.caption.lineHeight / typography.caption.fontSize,
    fontWeight: typography.caption.fontWeight,
    letterSpacing: typography.caption.letterSpacing,
  },
  button: {
    fontSize: typography.bodySmall.fontSize,
    lineHeight: typography.bodySmall.lineHeight / typography.bodySmall.fontSize,
    fontWeight: 600,
    letterSpacing: 0.5,
    textTransform: 'none',
  },
  overline: {
    fontSize: typography.caption.fontSize,
    lineHeight: typography.caption.lineHeight / typography.caption.fontSize,
    fontWeight: 700,
    letterSpacing: 1.5,
    textTransform: 'uppercase',
  },
};
