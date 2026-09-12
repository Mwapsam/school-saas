/**
 * Edit fee category page using design system components.
 */

'use client';

export const dynamic = 'force-dynamic';

import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { Button, Alert } from '@mui/material';
import { ChevronLeft as BackIcon } from '@mui/icons-material';
import { useTenantStore } from '@/lib/tenant/store';
import { useFeeCategory, useUpdateFeeCategory } from '@/features/finance/hooks';
import { FeeCategoryForm } from '@/features/finance/components/FeeCategoryForm';
import { Page } from '@/components/page/Page';
import { PageHeader } from '@/components/page/PageHeader';
import { PageContent } from '@/components/page/PageContent';
import { LoadingState } from '@/components/feedback/LoadingState';
import { ErrorState } from '@/components/feedback/ErrorState';

export default function EditFeeCategoryPage({ params }: { params: { id: string } }) {
  const router = useRouter();
  const { can, isModuleEnabled } = useTenantStore();
  const { data: feeCategory, isLoading: categoryLoading, error: categoryError, refetch } = useFeeCategory(params.id);
  const { mutateAsync: updateFeeCategory, error: updateError } = useUpdateFeeCategory(params.id);

  if (!isModuleEnabled('finance')) {
    return (
      <Page>
        <Alert severity="info">The Finance module is not enabled.</Alert>
      </Page>
    );
  }

  if (!can('finance.fees.manage')) {
    return (
      <Page>
        <Alert severity="error">You do not have permission to edit fee categories.</Alert>
      </Page>
    );
  }

  if (categoryLoading) {
    return (
      <Page>
        <LoadingState />
      </Page>
    );
  }

  if (categoryError || !feeCategory) {
    return (
      <Page>
        <ErrorState error={categoryError} onRetry={() => refetch()} />
      </Page>
    );
  }

  const handleSubmit = async (data: any) => {
    try {
      await updateFeeCategory(data);
      router.push(`/dashboard/invoices/fee-categories/${feeCategory.id}`);
    } catch (err) {
      console.error('Update failed:', err);
      throw err;
    }
  };

  return (
    <Page>
      <PageHeader
        title={`Edit Fee Category: ${feeCategory.name}`}
        breadcrumbs={
          <Link href={`/dashboard/invoices/fee-categories/${feeCategory.id}`} passHref legacyBehavior>
            <Button startIcon={<BackIcon />} variant="text">
              Back to Category
            </Button>
          </Link>
        }
      />

      <PageContent>
        {updateError && (
          <Alert severity="error" sx={{ mb: 3 }}>
            {(updateError as any)?.message || 'Failed to update fee category'}
          </Alert>
        )}

        <FeeCategoryForm
          feeCategory={feeCategory}
          error={(updateError as any)?.message}
          onSubmit={handleSubmit}
          onCancel={() => router.back()}
        />
      </PageContent>
    </Page>
  );
}
