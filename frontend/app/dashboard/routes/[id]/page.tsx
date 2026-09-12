/**
 * Transport route detail page using design system components.
 */

'use client';

export const dynamic = 'force-dynamic';

import Link from 'next/link';
import { Button, Box, Typography, Grid, Paper, Alert } from '@mui/material';
import { ChevronLeft as BackIcon } from '@mui/icons-material';
import { useTenantStore } from '@/lib/tenant/store';
import { useTransportRoute } from '@/features/transport/hooks';
import { Page } from '@/components/page/Page';
import { PageHeader } from '@/components/page/PageHeader';
import { PageContent } from '@/components/page/PageContent';
import { LoadingState } from '@/components/feedback/LoadingState';
import { ErrorState } from '@/components/feedback/ErrorState';

export default function TransportRouteDetailPage({ params }: { params: { id: string } }) {
  const { can, isModuleEnabled, bootstrap } = useTenantStore();
  const { data: route, isLoading, error, refetch } = useTransportRoute(params.id);

  if (!bootstrap) {
    return (
      <Page>
        <LoadingState />
      </Page>
    );
  }

  if (!isModuleEnabled('transport') || !can('transport.routes.view')) {
    return (
      <Page>
        <Alert severity="error">You do not have permission to view this route.</Alert>
      </Page>
    );
  }

  if (isLoading) {
    return (
      <Page>
        <LoadingState />
      </Page>
    );
  }

  if (error || !route) {
    return (
      <Page>
        <ErrorState error={error} onRetry={() => refetch()} />
      </Page>
    );
  }

  return (
    <Page>
      <PageHeader
        title={route.route_name}
        description={`Route Code: ${route.code}`}
        breadcrumbs={
          <Link href="/dashboard/routes" passHref legacyBehavior>
            <Button startIcon={<BackIcon />} variant="text">
              Back to Routes
            </Button>
          </Link>
        }
      />

      <PageContent>
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
                <Typography variant="body2">{route.route_name}</Typography>

                <Typography variant="body2" color="textSecondary">
                  Code:
                </Typography>
                <Typography variant="body2">{route.code}</Typography>

                <Typography variant="body2" color="textSecondary">
                  Fare:
                </Typography>
                <Typography variant="body2">{route.fare}</Typography>

                <Typography variant="body2" color="textSecondary">
                  Driver:
                </Typography>
                <Typography variant="body2">{route.driver_name || '-'}</Typography>

                <Typography variant="body2" color="textSecondary">
                  Attendant:
                </Typography>
                <Typography variant="body2">{route.attendant_name || '-'}</Typography>

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
      </PageContent>
    </Page>
  );
}
