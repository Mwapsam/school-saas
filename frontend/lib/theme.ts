/**
 * MUI theme factory.
 *
 * Builds the app theme from:
 * 1. Token-based design system (colors, typography, spacing, etc.)
 * 2. Tenant branding overrides (primary_color, secondary_color) when available
 *
 * All component styling is centralized in theme.components, so raw MUI usage
 * automatically inherits the product design without per-page sx overrides.
 */

import type { Theme } from '@mui/material/styles';
import { buildTheme as buildTokenTheme } from '@/design-system/theme/createTheme';
import type { BootstrapData } from './tenant/bootstrap';

/**
 * Create the MUI theme with optional tenant branding overrides.
 *
 * The theme includes:
 * - Full component style overrides (theme.components) from the design system
 * - Semantic tokens for colors, typography, spacing, etc.
 * - Tenant branding applied as palette overrides only (primary/secondary colors)
 *
 * Tenants can only change:
 * - Primary color
 * - Secondary color
 * - Typeface (when tenant.font_family is set — currently not yet implemented)
 *
 * Tenants cannot change:
 * - Spacing scale
 * - Border radius scale
 * - Component styling
 * - Typography scale (sizes, weights, line heights)
 */
export function buildTheme(bootstrap: BootstrapData | null): Theme {
  const tenantBranding = {
    primaryColor: bootstrap?.tenant?.primary_color,
    secondaryColor: bootstrap?.tenant?.secondary_color,
  };

  return buildTokenTheme(tenantBranding);
}
