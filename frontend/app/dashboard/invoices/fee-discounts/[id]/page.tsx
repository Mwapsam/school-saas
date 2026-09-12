/**
 * Fee discount detail view page using design system components.
 */

'use client';

export const dynamic = 'force-dynamic';

import Link from 'next/link';
import { Button, Grid, Alert } from '@mui/material';
import { Edit as EditIcon, ChevronLeft as BackIcon } from '@mui/icons-material';
import { useTenantStore } from '@/lib/tenant/store';
import { useFeeDiscount } from '@/features/finance/hooks';
import { Page } from '@/components/page/Page';
import { PageHeader } from '@/components/page/PageHeader';
import { PageContent } from '@/components/page/PageContent';
import { SectionCard, DetailField } from '@/components/page';
import { LoadingState } from '@/components/feedback/LoadingState';
import { ErrorState } from '@/components/feedback/ErrorState';
import { StatusBadge } from '@/components/data/StatusBadge';

export default function FeeDiscountDetailPage({ params }: { params: { id: string } }) {
  const { can, isModuleEnabled, bootstrap } = useTenantStore();
  const { data: feeDiscount, isLoading, error, refetch } = useFeeDiscount(params.id);

  if (!bootstrap) {
    return (
      <Page>
        <LoadingState />
      </Page>
    );
  }

  if (!isModuleEnabled('finance') || !can('finance.discounts.view')) {
    return (
      <Page>
        <Alert severity="error">You do not have permission to view this fee discount.</Alert>
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

  if (error || !feeDiscount) {
    return (
      <Page>
        <ErrorState error={error} onRetry={() => refetch()} />
      </Page>
    );
  }

  return (
    <Page>
      <PageHeader
        title={feeDiscount.name}
        breadcrumbs={
          <Link href="/dashboard/invoices/fee-discounts" passHref legacyBehavior>
            <Button startIcon={<BackIcon />} variant="text">
              Back to Discounts
            </Button>
          </Link>
        }
        actions={
          can('finance.discounts.manage') && (
            <Link href={`/dashboard/invoices/fee-discounts/${feeDiscount.id}/edit`} passHref legacyBehavior>
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
            <SectionCard title="Fee Discount Information">
              <DetailField label="Name" value={feeDiscount.name} />
              <DetailField label="Fee Category" value={feeDiscount.fee_category_name || '-'} />
              <DetailField
                label="Discount Type"
                value={feeDiscount.discount_type === 'batch' ? 'Batch Discount' : 'Individual Discount'}
              />
              <DetailField label="Discount Value" value={feeDiscount.discount_value} />
              <DetailField
                label="Status"
                value={
                  <StatusBadge
                    label={feeDiscount.is_active ? 'Active' : 'Inactive'}
                    status={feeDiscount.is_active ? 'success' : 'error'}
                  />
                }
              />
              <DetailField label="Created" value={new Date(feeDiscount.created_at).toLocaleDateString()} />
              <DetailField label="Updated" value={new Date(feeDiscount.updated_at).toLocaleDateString()} />
            </SectionCard>
          </Grid>
        </Grid>
      </PageContent>
    </Page>
  );
}
