'use client';

import { useEffect, useState, type ReactNode } from 'react';
import { Box, Drawer, Toolbar, CircularProgress, Container, Alert } from '@mui/material';
import { useTenantStore } from '@/lib/tenant/store';
import { fetchBootstrap } from '@/lib/tenant/bootstrap';
import { Sidebar } from './Sidebar';
import { TopBar } from './TopBar';
import { Breadcrumbs } from './Breadcrumbs';

const DRAWER_WIDTH = 260;

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

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
        <CircularProgress />
      </Box>
    );
  }

  if (error || !bootstrap) {
    return (
      <Container maxWidth="sm">
        <Box sx={{ py: 8 }}>
          <Alert severity="error">{error || 'No configuration loaded'}</Alert>
        </Box>
      </Container>
    );
  }

  const drawerContent = <Sidebar onNavigate={() => setMobileOpen(false)} />;

  return (
    <Box sx={{ display: 'flex' }}>
      <TopBar onMenuClick={() => setMobileOpen((open) => !open)} />

      <Box component="nav" sx={{ width: { md: DRAWER_WIDTH }, flexShrink: { md: 0 } }}>
        {/* Mobile: temporary overlay drawer */}
        <Drawer
          variant="temporary"
          open={mobileOpen}
          onClose={() => setMobileOpen(false)}
          ModalProps={{ keepMounted: true }}
          sx={{
            display: { xs: 'block', md: 'none' },
            '& .MuiDrawer-paper': { boxSizing: 'border-box', width: DRAWER_WIDTH },
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
            '& .MuiDrawer-paper': { boxSizing: 'border-box', width: DRAWER_WIDTH },
          }}
          open
        >
          <Toolbar />
          {drawerContent}
        </Drawer>
      </Box>

      <Box
        component="main"
        sx={{
          flexGrow: 1,
          width: { md: `calc(100% - ${DRAWER_WIDTH}px)` },
          minHeight: '100vh',
          bgcolor: 'grey.50',
        }}
      >
        <Toolbar />
        <Container maxWidth="lg" sx={{ py: 3 }}>
          <Breadcrumbs />
          {children}
        </Container>
      </Box>
    </Box>
  );
}
