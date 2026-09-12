/**
 * Edit fee discount page using design system components.
 */

'use client';

export const dynamic = 'force-dynamic';

import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { Button, Alert } from '@mui/material';
import { ChevronLeft as BackIcon } from '@mui/icons-material';
import { useTenantStore } from '@/lib/tenant/store';
import { useFeeDiscount, useUpdateFeeDiscount } from '@/features/finance/hooks';
import { FeeDiscountForm } from '@/features/finance/components/FeeDiscountForm';
import { Page } from '@/components/page/Page';
import { PageHeader } from '@/components/page/PageHeader';
import { PageContent } from '@/components/page/PageContent';
import { LoadingState } from '@/components/feedback/LoadingState';
import { ErrorState } from '@/components/feedback/ErrorState';

export default function EditFeeDiscountPage({ params }: { params: { id: string } }) {
  const router = useRouter();
  const { can, isModuleEnabled } = useTenantStore();
  const { data: feeDiscount, isLoading: discountLoading, error: discountError, refetch } = useFeeDiscount(params.id);
  const { mutateAsync: updateFeeDiscount, error: updateError } = useUpdateFeeDiscount(params.id);

  if (!isModuleEnabled('finance')) {
    return (
      <Page>
        <Alert severity="info">The Finance module is not enabled.</Alert>
      </Page>
    );
  }

  if (!can('finance.discounts.manage')) {
    return (
      <Page>
        <Alert severity="error">You do not have permission to edit fee discounts.</Alert>
      </Page>
    );
  }

  if (discountLoading) {
    return (
      <Page>
        <LoadingState />
      </Page>
    );
  }

  if (discountError || !feeDiscount) {
    return (
      <Page>
        <ErrorState error={discountError} onRetry={() => refetch()} />
      </Page>
    );
  }

  const handleSubmit = async (data: any) => {
    try {
      await updateFeeDiscount(data);
      router.push(`/dashboard/invoices/fee-discounts/${feeDiscount.id}`);
    } catch (err) {
      console.error('Update failed:', err);
      throw err;
    }
  };

  return (
    <Page>
      <PageHeader
        title={`Edit Fee Discount: ${feeDiscount.name}`}
        breadcrumbs={
          <Link href={`/dashboard/invoices/fee-discounts/${feeDiscount.id}`} passHref legacyBehavior>
            <Button startIcon={<BackIcon />} variant="text">
              Back to Discount
            </Button>
          </Link>
        }
      />

      <PageContent>
        {updateError && (
          <Alert severity="error" sx={{ mb: 3 }}>
            {(updateError as any)?.message || 'Failed to update fee discount'}
          </Alert>
        )}

        <FeeDiscountForm
          feeDiscount={feeDiscount}
          error={(updateError as any)?.message}
          onSubmit={handleSubmit}
          onCancel={() => router.back()}
        />
      </PageContent>
    </Page>
  );
}
