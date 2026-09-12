/**
 * Hostel room detail page using design system components.
 */

'use client';

export const dynamic = 'force-dynamic';

import Link from 'next/link';
import { Button, Grid, Alert } from '@mui/material';
import { ChevronLeft as BackIcon } from '@mui/icons-material';
import { useTenantStore } from '@/lib/tenant/store';
import { useHostelRoom } from '@/features/hostel/hooks';
import { Page } from '@/components/page/Page';
import { PageHeader } from '@/components/page/PageHeader';
import { PageContent } from '@/components/page/PageContent';
import { SectionCard, DetailField } from '@/components/page';
import { LoadingState } from '@/components/feedback/LoadingState';
import { ErrorState } from '@/components/feedback/ErrorState';

export default function HostelRoomDetailPage({ params }: { params: { id: string } }) {
  const { can, isModuleEnabled, bootstrap } = useTenantStore();
  const { data: room, isLoading, error, refetch } = useHostelRoom(params.id);

  if (!bootstrap) {
    return (
      <Page>
        <LoadingState />
      </Page>
    );
  }

  if (!isModuleEnabled('hostel') || !can('hostel.rooms.view')) {
    return (
      <Page>
        <Alert severity="error">You do not have permission to view this hostel room.</Alert>
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

  if (error || !room) {
    return (
      <Page>
        <ErrorState error={error} onRetry={() => refetch()} />
      </Page>
    );
  }

  return (
    <Page>
      <PageHeader
        title={`Room ${room.room_number}`}
        description={`${room.room_type} • Capacity: ${room.capacity}`}
        breadcrumbs={
          <Link href="/dashboard/hostel-rooms" passHref legacyBehavior>
            <Button startIcon={<BackIcon />} variant="text">
              Back to Rooms
            </Button>
          </Link>
        }
      />

      <PageContent>
        <Grid container spacing={3}>
          <Grid item xs={12} md={6}>
            <SectionCard title="Room Information">
              <DetailField label="Room Number" value={room.room_number} />
              <DetailField label="Room Type" value={room.room_type} />
              <DetailField label="Capacity" value={room.capacity} />
              <DetailField label="Rent" value={room.rent} />
              <DetailField label="Created" value={new Date(room.created_at).toLocaleDateString()} />
            </SectionCard>
          </Grid>
        </Grid>
      </PageContent>
    </Page>
  );
}
