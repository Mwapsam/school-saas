'use client';

import { useEffect, useState, type ReactNode } from 'react';
import { Box, Drawer, Toolbar, CircularProgress, Container, Alert } from '@mui/material';
import { useTenantStore } from '@/lib/tenant/store';
import { fetchBootstrap } from '@/lib/tenant/bootstrap';
import { Sidebar } from './Sidebar';
import { TopBar } from './TopBar';
import { Breadcrumbs } from './Breadcrumbs';
import { colors, spacing } from '@/design-system/tokens';

const EXPANDED_WIDTH = 280;
const COLLAPSED_WIDTH = 72;

/**
 * Main application shell.
 *
 * Provides the layout structure: TopBar + Sidebar + content area.
 * Handles responsive design (permanent sidebar on desktop, temporary drawer on mobile).
 * Loads bootstrap data (tenant config, user info, capabilities) on mount.
 * Supports collapsible desktop sidebar with smooth width transitions.
 */
export function DashboardShell({ children }: { children: ReactNode }) {
  const { bootstrap, setBootstrap, setLoading, loading } = useTenantStore();
  const [error, setError] = useState<string | null>(null);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [collapsed, setCollapsed] = useState(false);

  const desktopWidth = collapsed ? COLLAPSED_WIDTH : EXPANDED_WIDTH;

  useEffect(() => {
    if (bootstrap) return;

    let cancelled = false;
    async function loadBootstrap() {
      setLoading(true);
      try {
        const data = await fetchBootstrap();
        if (!cancelled) setBootstrap(data);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Failed to load configuration');
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    loadBootstrap();
    return () => {
      cancelled = true;
    };
  }, [bootstrap, setBootstrap, setLoading]);

  if (loading) {
    return (
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          height: '100vh',
          backgroundColor: colors.background.default,
        }}
      >
        <CircularProgress />
      </Box>
    );
  }

  if (error || !bootstrap) {
    return (
      <Container maxWidth="sm">
        <Box sx={{ py: spacing['2xl'] }}>
          <Alert severity="error">{error || 'No configuration loaded'}</Alert>
        </Box>
      </Container>
    );
  }

  // Mobile always gets the full expanded sidebar
  const mobileDrawerContent = (
    <Sidebar onNavigate={() => setMobileOpen(false)} collapsed={false} />
  );

  // Desktop uses the controlled collapsed state
  const desktopDrawerContent = (
    <Sidebar
      onNavigate={() => setMobileOpen(false)}
      collapsed={collapsed}
      onCollapsedChange={setCollapsed}
    />
  );

  return (
    <Box sx={{ display: 'flex', height: '100vh' }}>
      <TopBar onMenuClick={() => setMobileOpen((open) => !open)} />

      <Box
        component="nav"
        sx={{
          width: { md: desktopWidth },
          flexShrink: { md: 0 },
          transition: 'width 220ms cubic-bezier(0.4, 0, 0.2, 1)',
          '@media (prefers-reduced-motion: reduce)': { transition: 'none' },
        }}
      >
        {/* Mobile: temporary overlay drawer */}
        <Drawer
          variant="temporary"
          open={mobileOpen}
          onClose={() => setMobileOpen(false)}
          ModalProps={{ keepMounted: true }}
          sx={{
            display: { xs: 'block', md: 'none' },
            '& .MuiDrawer-paper': {
              boxSizing: 'border-box',
              width: EXPANDED_WIDTH,
              backgroundColor: colors.background.surface,
              borderRight: `1px solid ${colors.border.default}`,
            },
          }}
        >
          <Toolbar />
          {mobileDrawerContent}
        </Drawer>

        {/* Desktop: permanent drawer with dynamic width */}
        <Drawer
          variant="permanent"
          sx={{
            display: { xs: 'none', md: 'block' },
            '& .MuiDrawer-paper': {
              boxSizing: 'border-box',
              width: desktopWidth,
              backgroundColor: colors.background.surface,
              borderRight: `1px solid ${colors.border.default}`,
              position: 'fixed',
              height: '100vh',
              top: 0,
              left: 0,
              transition: 'width 220ms cubic-bezier(0.4, 0, 0.2, 1)',
              overflowX: 'hidden',
              '@media (prefers-reduced-motion: reduce)': { transition: 'none' },
            },
          }}
          open
        >
          <Toolbar />
          {desktopDrawerContent}
        </Drawer>
      </Box>

      {/* Main content — follows sidebar width */}
      <Box
        component="main"
        sx={{
          flexGrow: 1,
          width: { md: `calc(100% - ${desktopWidth}px)` },
          minHeight: '100vh',
          display: 'flex',
          flexDirection: 'column',
          backgroundColor: colors.background.default,
          overflowY: 'auto',
          ml: { xs: 0, md: `${desktopWidth}px` },
          transition:
            'margin-left 220ms cubic-bezier(0.4, 0, 0.2, 1), width 220ms cubic-bezier(0.4, 0, 0.2, 1)',
          '@media (prefers-reduced-motion: reduce)': { transition: 'none' },
        }}
      >
        <Toolbar sx={{ minHeight: 64 }} />

        <Box
          sx={{
            flex: 1,
            overflow: 'auto',
            py: spacing.pageVertical,
            px: spacing.pageHorizontal,
          }}
        >
          <Container maxWidth="lg">
            <Breadcrumbs />
            {children}
          </Container>
        </Box>
      </Box>
    </Box>
  );
}