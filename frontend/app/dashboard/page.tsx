/**
 * Dashboard home page — entry point after login.
 *
 * Fetches and displays:
 * - Bootstrap data (tenant config, user info, modules, capabilities)
 * - Navigation based on enabled modules
 * - Tenant branding (logo, colors, name)
 */

'use client';

import { useEffect, useState } from 'react';
import { Container, Box, Typography, Grid, CircularProgress } from '@mui/material';
import { useTenantStore } from '@/lib/tenant/store';
import { fetchBootstrap } from '@/lib/tenant/bootstrap';

export default function DashboardPage() {
  const { bootstrap, setBootstrap, setLoading, loading } = useTenantStore();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function loadBootstrap() {
      if (bootstrap) return; // Already loaded

      setLoading(true);
      try {
        const data = await fetchBootstrap();
        setBootstrap(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load configuration');
        setLoading(false);
      }
    }

    loadBootstrap();
  }, [bootstrap, setBootstrap, setLoading]);

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
        <CircularProgress />
      </Box>
    );
  }

  if (error) {
    return (
      <Container>
        <Box sx={{ py: 4 }}>
          <Typography color="error">{error}</Typography>
        </Box>
      </Container>
    );
  }

  if (!bootstrap) {
    return (
      <Container>
        <Box sx={{ py: 4 }}>
          <Typography>No configuration loaded</Typography>
        </Box>
      </Container>
    );
  }

  return (
    <Container maxWidth="lg">
      <Box sx={{ py: 4 }}>
        <Typography variant="h3" gutterBottom>
          Welcome, {bootstrap.user.full_name}
        </Typography>

        <Grid container spacing={3} sx={{ mt: 2 }}>
          <Grid item xs={12}>
            <Box sx={{ p: 2, border: '1px solid #ddd', borderRadius: 1 }}>
              <Typography variant="h6">Tenant: {bootstrap.tenant.name}</Typography>
              <Typography variant="body2" color="textSecondary">
                Code: {bootstrap.tenant.code}
              </Typography>
            </Box>
          </Grid>

          <Grid item xs={12}>
            <Typography variant="h6">Enabled Modules</Typography>
            <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', mt: 1 }}>
              {Object.entries(bootstrap.modules)
                .filter(([_, enabled]) => enabled)
                .map(([module]) => (
                  <Box
                    key={module}
                    sx={{ px: 2, py: 1, bgcolor: '#e3f2fd', borderRadius: 1 }}
                  >
                    <Typography variant="body2">{module}</Typography>
                  </Box>
                ))}
            </Box>
          </Grid>

          <Grid item xs={12}>
            <Typography variant="h6">Capabilities</Typography>
            <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap', fontFamily: 'monospace', mt: 1 }}>
              {bootstrap.capabilities.join('\n')}
            </Typography>
          </Grid>
        </Grid>

        {/* TODO: Render domain-specific dashboard sections based on enabled modules */}
      </Box>
    </Container>
  );
}
