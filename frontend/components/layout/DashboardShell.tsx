'use client';

import { useEffect, useState, type ReactNode } from 'react';
import { Box, Drawer, Toolbar, CircularProgress, Container, Alert } from '@mui/material';
import { useTenantStore } from '@/lib/tenant/store';
import { fetchBootstrap } from '@/lib/tenant/bootstrap';
import { Sidebar } from './Sidebar';
import { TopBar } from './TopBar';
import { Breadcrumbs } from './Breadcrumbs';
import { colors, spacing } from '@/design-system/tokens';

const DRAWER_WIDTH = 260;

/**
 * Main application shell.
 *
 * Provides the layout structure: TopBar + Sidebar + content area.
 * Handles responsive design (permanent sidebar on desktop, temporary drawer on mobile).
 * Loads bootstrap data (tenant config, user info, capabilities) on mount.
 */
export function DashboardShell({ children }: { children: ReactNode }) {
  const { bootstrap, setBootstrap, setLoading, loading } = useTenantStore();
  const [error, setError] = useState<string | null>(null);
  const [mobileOpen, setMobileOpen] = useState(false);

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

  // Loading state
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

  // Error state
  if (error || !bootstrap) {
    return (
      <Container maxWidth="sm">
        <Box sx={{ py: spacing['2xl'] }}>
          <Alert severity="error">{error || 'No configuration loaded'}</Alert>
        </Box>
      </Container>
    );
  }

  const drawerContent = <Sidebar onNavigate={() => setMobileOpen(false)} />;

  return (
    <Box sx={{ display: 'flex', height: '100vh' }}>
      {/* Top navigation bar */}
      <TopBar onMenuClick={() => setMobileOpen((open) => !open)} />

      {/* Sidebar navigation */}
      <Box component="nav" sx={{ width: { md: DRAWER_WIDTH }, flexShrink: { md: 0 } }}>
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
              width: DRAWER_WIDTH,
              backgroundColor: colors.background.surface,
              borderRight: `1px solid ${colors.border.default}`,
            },
          }}
        >
          <Toolbar />
          {drawerContent}
        </Drawer>

        {/* Desktop: permanent drawer */}
        <Drawer
          variant="permanent"
          sx={{
            display: { xs: 'none', md: 'block' },
            '& .MuiDrawer-paper': {
              boxSizing: 'border-box',
              width: DRAWER_WIDTH,
              backgroundColor: colors.background.surface,
              borderRight: `1px solid ${colors.border.default}`,
              position: 'fixed',
              height: '100vh',
              top: 0,
              left: 0,
            },
          }}
          open
        >
          <Toolbar />
          {drawerContent}
        </Drawer>
      </Box>

      {/* Main content area */}
      <Box
        component="main"
        sx={{
          flexGrow: 1,
          width: { md: `calc(100% - ${DRAWER_WIDTH}px)` },
          minHeight: '100vh',
          display: 'flex',
          flexDirection: 'column',
          backgroundColor: colors.background.default,
          overflowY: 'auto',
          ml: { xs: 0, md: `${DRAWER_WIDTH}px` },
        }}
      >
        {/* Fixed top bar spacing */}
        <Toolbar sx={{ minHeight: 64 }} />

        {/* Page content */}
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
