/**
 * Motion scale tokens.
 *
 * Durations and easing for consistent, subtle animations throughout the app.
 * Never changed per tenant.
 */

export const motion = {
  // Durations
  fast: 120,     // quick feedback: hover, icon changes, brief transitions
  normal: 180,   // standard: drawer open, menu open, typical transitions
  slow: 250,     // longer: dialog enter, major state changes

  // Easing (cubic-bezier format)
  // Standard MUI easing: ease-in-out
  easing: 'cubic-bezier(0.4, 0, 0.2, 1)',

  // Alternative easings
  easeIn: 'cubic-bezier(0.4, 0, 1, 1)',
  easeOut: 'cubic-bezier(0, 0, 0.2, 1)',
  easeInOut: 'cubic-bezier(0.4, 0, 0.2, 1)',
};

/**
 * Transition helpers for consistent animation definitions
 */
export const transitions = {
  // Fast transitions (hover states, icon changes)
  fast: `${motion.fast}ms ${motion.easing}`,
  fastIn: `${motion.fast}ms ${motion.easeIn}`,
  fastOut: `${motion.fast}ms ${motion.easeOut}`,

  // Normal transitions (standard interactions)
  normal: `${motion.normal}ms ${motion.easing}`,
  normalIn: `${motion.normal}ms ${motion.easeIn}`,
  normalOut: `${motion.normal}ms ${motion.easeOut}`,

  // Slow transitions (major state changes)
  slow: `${motion.slow}ms ${motion.easing}`,
  slowIn: `${motion.slow}ms ${motion.easeIn}`,
  slowOut: `${motion.slow}ms ${motion.easeOut}`,
};

/**
 * MUI transition configuration
 */
export const muiTransitions = {
  duration: {
    shortest: motion.fast,
    shorter: motion.fast,
    short: motion.normal,
    standard: motion.normal,
    complex: motion.slow,
  },
  easing: {
    easeInOut: motion.easing,
    easeOut: motion.easeOut,
    easeIn: motion.easeIn,
    linear: 'linear',
  },
};
