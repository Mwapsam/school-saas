/**
 * Transport route detail view page (read-only, Phase 1).
 */

'use client';

export const dynamic = 'force-dynamic';

import { useRouter } from 'next/navigation';
import { Container, Box, Typography, Button, Grid, Paper, CircularProgress, Alert } from '@mui/material';
import { ArrowBack as BackIcon } from '@mui/icons-material';
import { useTenantStore } from '@/lib/tenant/store';
import { useTransportRoute } from '@/features/transport/hooks';

export default function TransportRouteDetailPage({ params }: { params: { id: string } }) {
  const router = useRouter();
  const { can, isModuleEnabled, bootstrap } = useTenantStore();
  const { data: route, isLoading, error } = useTransportRoute(params.id);

  if (!bootstrap) {
    return (
      <Container maxWidth="lg">
        <Box sx={{ py: 4 }}>
          <Typography>Loading configuration...</Typography>
        </Box>
      </Container>
    );
  }

  if (!isModuleEnabled('transport') || !can('transport.view')) {
    return (
      <Container maxWidth="lg">
        <Box sx={{ py: 4 }}>
          <Alert severity="error">
            You do not have permission to view this route.
          </Alert>
        </Box>
      </Container>
    );
  }

  if (isLoading) {
    return (
      <Container maxWidth="lg">
        <Box sx={{ py: 4, display: 'flex', justifyContent: 'center' }}>
          <CircularProgress />
        </Box>
      </Container>
    );
  }

  if (error || !route) {
    return (
      <Container maxWidth="lg">
        <Box sx={{ py: 4 }}>
          <Alert severity="error">
            Failed to load route: {error?.message || 'Route not found'}
          </Alert>
        </Box>
      </Container>
    );
  }

  return (
    <Container maxWidth="lg">
      <Box sx={{ py: 4 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 3 }}>
          <Button startIcon={<BackIcon />} onClick={() => router.back()} variant="text">
            Back
          </Button>
          <Typography variant="h4" component="h1">
            {route.name}
          </Typography>
        </Box>

        <Grid container spacing={3}>
          <Grid item xs={12} md={6}>
            <Paper sx={{ p: 2 }}>
              <Typography variant="h6" gutterBottom>
                Route Information
              </Typography>
              <Box sx={{ display: 'grid', gridTemplateColumns: '150px 1fr', gap: 1 }}>
                <Typography variant="body2" color="textSecondary">
                  Name:
                </Typography>
                <Typography variant="body2">{route.name}</Typography>

                <Typography variant="body2" color="textSecondary">
                  Code:
                </Typography>
                <Typography variant="body2">{route.code}</Typography>

                <Typography variant="body2" color="textSecondary">
                  Type:
                </Typography>
                <Typography variant="body2">{route.route_type}</Typography>

                <Typography variant="body2" color="textSecondary">
                  Vehicle:
                </Typography>
                <Typography variant="body2">{route.vehicle_name || '-'}</Typography>

                <Typography variant="body2" color="textSecondary">
                  Students:
                </Typography>
                <Typography variant="body2">{route.student_count}</Typography>

                <Typography variant="body2" color="textSecondary">
                  Created:
                </Typography>
                <Typography variant="body2">
                  {new Date(route.created_at).toLocaleDateString()}
                </Typography>
              </Box>
            </Paper>
          </Grid>
        </Grid>
      </Box>
    </Container>
  );
}
