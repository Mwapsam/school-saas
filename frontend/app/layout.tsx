/**
 * Root layout — sets up global context providers.
 *
 * Provides:
 * - MUI theme (generated from bootstrap colors)
 * - React Query (for data fetching/caching)
 * - Tenant store (Zustand)
 */

import type { Metadata } from 'next';
import { ThemeProvider } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';
import { createTheme } from '@mui/material/styles';

export const metadata: Metadata = {
  title: 'School Management Platform',
  description: 'Multi-tenant school management system',
};

// Default theme — will be overridden by bootstrap colors
const defaultTheme = createTheme({
  palette: {
    primary: {
      main: '#1976d2',
    },
    secondary: {
      main: '#dc004e',
    },
  },
  typography: {
    fontFamily: [
      '-apple-system',
      'BlinkMacSystemFont',
      '"Segoe UI"',
      'Roboto',
      '"Helvetica Neue"',
      'Arial',
      'sans-serif',
    ].join(','),
  },
});

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <ThemeProvider theme={defaultTheme}>
          <CssBaseline />
          {/* TODO: Wrap children with providers */}
          {children}
        </ThemeProvider>
      </body>
    </html>
  );
}
