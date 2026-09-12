'use client';

import { useTheme, useMediaQuery } from '@mui/material';

/**
 * Responsive sidebar width configuration based on screen size.
 *
 * Desktop (lg+):     expanded 280px, collapsed 72px
 * Tablet (md-lg):    expanded 240px, collapsed 64px
 * Mobile (sm-md):    hidden (overlay drawer only)
 */
export const SIDEBAR_WIDTHS = {
  desktop: {
    expanded: 280,
    collapsed: 72,
  },
  tablet: {
    expanded: 240,
    collapsed: 64,
  },
  mobile: {
    expanded: 260,     // Mobile drawer width (from Sidebar EXPANDED_WIDTH)
    collapsed: 0,      // Collapsed not used on mobile
  },
} as const;

/**
 * Hook that returns responsive sidebar width based on screen size and collapsed state.
 *
 * @param collapsed - Whether sidebar is in collapsed mode
 * @returns Width in pixels
 */
export function useSidebarWidth(collapsed: boolean): number {
  const theme = useTheme();
  const isDesktop = useMediaQuery(theme.breakpoints.up('lg'));
  const isTablet = useMediaQuery(theme.breakpoints.between('md', 'lg'));

  // Mobile: no permanent sidebar (drawer overlay only)
  if (!isDesktop && !isTablet) {
    return 0;
  }

  // Tablet: narrower sidebar
  if (isTablet) {
    return collapsed ? SIDEBAR_WIDTHS.tablet.collapsed : SIDEBAR_WIDTHS.tablet.expanded;
  }

  // Desktop: full width sidebar
  return collapsed ? SIDEBAR_WIDTHS.desktop.collapsed : SIDEBAR_WIDTHS.desktop.expanded;
}
