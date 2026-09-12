/**
 * Root layout — sets up global context providers.
 *
 * Provides:
 * - MUI theme (generated from bootstrap colors)
 * - React Query (for data fetching/caching)
 * - Tenant store (Zustand)
 */

import type { Metadata } from 'next';
import Providers from './providers';

export const metadata: Metadata = {
  title: 'School Management Platform',
  description: 'Multi-tenant school management system',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body>
        <Providers>
          {children}
        </Providers>
      </body>
    </html>
  );
}
