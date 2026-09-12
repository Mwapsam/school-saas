/**
 * MUI theme factory.
 *
 * Builds the app theme from tenant branding colors (bootstrap.tenant.primary_color /
 * secondary_color) when available, falling back to platform defaults before
 * bootstrap has loaded or when a tenant hasn't set custom colors.
 */

import { createTheme, type Theme } from '@mui/material/styles';
import type { BootstrapData } from './tenant/bootstrap';

const DEFAULT_PRIMARY = '#1976d2';
const DEFAULT_SECONDARY = '#dc004e';

const FONT_FAMILY = [
  '-apple-system',
  'BlinkMacSystemFont',
  '"Segoe UI"',
  'Roboto',
  '"Helvetica Neue"',
  'Arial',
  'sans-serif',
].join(',');

export function buildTheme(bootstrap: BootstrapData | null): Theme {
  const primary = bootstrap?.tenant?.primary_color || DEFAULT_PRIMARY;
  const secondary = bootstrap?.tenant?.secondary_color || DEFAULT_SECONDARY;

  return createTheme({
    palette: {
      primary: { main: primary },
      secondary: { main: secondary },
    },
    typography: {
      fontFamily: FONT_FAMILY,
    },
    shape: {
      borderRadius: 8,
    },
  });
}
