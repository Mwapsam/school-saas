/**
 * Fee discount detail view page using design system components.
 */

'use client';

export const dynamic = 'force-dynamic';

import Link from 'next/link';
import { Button, Box, Typography, Grid, Paper, Alert } from '@mui/material';
import { Edit as EditIcon, ChevronLeft as BackIcon } from '@mui/icons-material';
import { useTenantStore } from '@/lib/tenant/store';
import { useFeeDiscount } from '@/features/finance/hooks';
import { Page } from '@/components/page/Page';
import { PageHeader } from '@/components/page/PageHeader';
import { PageContent } from '@/components/page/PageContent';
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
            <Paper sx={{ p: 2 }}>
              <Typography variant="h6" gutterBottom>
                Fee Discount Information
              </Typography>
              <Box sx={{ display: 'grid', gridTemplateColumns: '150px 1fr', gap: 1 }}>
                <Typography variant="body2" color="textSecondary">
                  Name:
                </Typography>
                <Typography variant="body2">{feeDiscount.name}</Typography>

                <Typography variant="body2" color="textSecondary">
                  Fee Category:
                </Typography>
                <Typography variant="body2">{feeDiscount.fee_category_name || '-'}</Typography>

                <Typography variant="body2" color="textSecondary">
                  Discount Type:
                </Typography>
                <Typography variant="body2">
                  {feeDiscount.discount_type === 'batch' ? 'Batch Discount' : 'Individual Discount'}
                </Typography>

                <Typography variant="body2" color="textSecondary">
                  Discount Value:
                </Typography>
                <Typography variant="body2">{feeDiscount.discount_value}</Typography>

                <Typography variant="body2" color="textSecondary">
                  Status:
                </Typography>
                <StatusBadge status={feeDiscount.is_active ? 'active' : 'inactive'} />

                <Typography variant="body2" color="textSecondary">
                  Created:
                </Typography>
                <Typography variant="body2">
                  {new Date(feeDiscount.created_at).toLocaleDateString()}
                </Typography>

                <Typography variant="body2" color="textSecondary">
                  Updated:
                </Typography>
                <Typography variant="body2">
                  {new Date(feeDiscount.updated_at).toLocaleDateString()}
                </Typography>
              </Box>
            </Paper>
          </Grid>
        </Grid>
      </PageContent>
    </Page>
  );
}
