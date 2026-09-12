/**
 * Transport route detail page using design system components.
 */

'use client';

export const dynamic = 'force-dynamic';

import Link from 'next/link';
import { Button, Grid, Alert } from '@mui/material';
import { ChevronLeft as BackIcon } from '@mui/icons-material';
import { useTenantStore } from '@/lib/tenant/store';
import { useTransportRoute } from '@/features/transport/hooks';
import { Page } from '@/components/page/Page';
import { PageHeader } from '@/components/page/PageHeader';
import { PageContent } from '@/components/page/PageContent';
import { SectionCard, DetailField } from '@/components/page';
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
            <SectionCard title="Route Information">
              <DetailField label="Name" value={route.route_name} />
              <DetailField label="Code" value={route.code} />
              <DetailField label="Fare" value={route.fare} />
              <DetailField label="Driver" value={route.driver_name || '-'} />
              <DetailField label="Attendant" value={route.attendant_name || '-'} />
              <DetailField label="Created" value={new Date(route.created_at).toLocaleDateString()} />
            </SectionCard>
          </Grid>
        </Grid>
      </PageContent>
    </Page>
  );
}
