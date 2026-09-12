/**
 * Fee category detail view page using design system components.
 */

'use client';

export const dynamic = 'force-dynamic';

import Link from 'next/link';
import { Button, Grid, Alert } from '@mui/material';
import { Edit as EditIcon, ChevronLeft as BackIcon } from '@mui/icons-material';
import { useTenantStore } from '@/lib/tenant/store';
import { useFeeCategory } from '@/features/finance/hooks';
import { Page } from '@/components/page/Page';
import { PageHeader } from '@/components/page/PageHeader';
import { PageContent } from '@/components/page/PageContent';
import { SectionCard, DetailField } from '@/components/page';
import { LoadingState } from '@/components/feedback/LoadingState';
import { ErrorState } from '@/components/feedback/ErrorState';

export default function FeeCategoryDetailPage({ params }: { params: { id: string } }) {
  const { can, isModuleEnabled, bootstrap } = useTenantStore();
  const { data: feeCategory, isLoading, error, refetch } = useFeeCategory(params.id);

  if (!bootstrap) {
    return (
      <Page>
        <LoadingState />
      </Page>
    );
  }

  if (!isModuleEnabled('finance') || !can('finance.fees.view')) {
    return (
      <Page>
        <Alert severity="error">You do not have permission to view this fee category.</Alert>
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

  if (error || !feeCategory) {
    return (
      <Page>
        <ErrorState error={error} onRetry={() => refetch()} />
      </Page>
    );
  }

  return (
    <Page>
      <PageHeader
        title={feeCategory.name}
        description={feeCategory.description || undefined}
        breadcrumbs={
          <Link href="/dashboard/invoices/fee-categories" passHref legacyBehavior>
            <Button startIcon={<BackIcon />} variant="text">
              Back to Categories
            </Button>
          </Link>
        }
        actions={
          can('finance.fees.manage') && (
            <Link href={`/dashboard/invoices/fee-categories/${feeCategory.id}/edit`} passHref legacyBehavior>
              <Button component="a" variant="contained" startIcon={<EditIcon />}>
                Edit
              </Button>
            </Link>
          )
        }
      />

      <PageContent>
        <Grid container spacing={3}>
          <Grid item xs={12} md={6}>
            <SectionCard title="Fee Category Information">
              <DetailField label="Name" value={feeCategory.name} />
              <DetailField label="Description" value={feeCategory.description || '-'} />
              <DetailField label="Academic Year" value={feeCategory.academic_year_label || '-'} />
              <DetailField label="Created" value={new Date(feeCategory.created_at).toLocaleDateString()} />
              <DetailField label="Updated" value={new Date(feeCategory.updated_at).toLocaleDateString()} />
            </SectionCard>
          </Grid>
        </Grid>
      </PageContent>
    </Page>
  );
}
