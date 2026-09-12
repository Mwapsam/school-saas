/**
 * Density scale tokens.
 *
 * Defines comfortable, compact, and dense spacing presets.
 * Currently shipping only "comfortable" — others defined for future use.
 */

export type Density = 'comfortable' | 'compact' | 'dense';

export const density = {
  comfortable: {
    pageSpacing: 32,
    sectionSpacing: 24,
    tableRowHeight: 52,
    inputHeight: 40,
    buttonHeight: 40,
    componentPadding: 16,
  },

  compact: {
    pageSpacing: 24,
    sectionSpacing: 16,
    tableRowHeight: 44,
    inputHeight: 36,
    buttonHeight: 36,
    componentPadding: 12,
  },

  dense: {
    pageSpacing: 16,
    sectionSpacing: 12,
    tableRowHeight: 36,
    inputHeight: 32,
    buttonHeight: 32,
    componentPadding: 8,
  },
};

/**
 * Default density for the application.
 * Not a user toggle initially — it's a system-wide preset.
 */
export const defaultDensity: Density = 'comfortable';

/**
 * Get density config for a given density level
 */
export const getDensity = (level: Density = defaultDensity) => density[level];
