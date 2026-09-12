/**
 * Edit fee category page.
 */

'use client';

export const dynamic = 'force-dynamic';

import { useRouter } from 'next/navigation';
import { Container, Box, Typography, Alert, CircularProgress } from '@mui/material';
import { useTenantStore } from '@/lib/tenant/store';
import { useFeeCategory, useUpdateFeeCategory } from '@/features/finance/hooks';
import { FeeCategoryForm } from '@/features/finance/components/FeeCategoryForm';

export default function EditFeeCategoryPage({ params }: { params: { id: string } }) {
  const router = useRouter();
  const { can, isModuleEnabled } = useTenantStore();
  const { data: feeCategory, isLoading: categoryLoading, error: categoryError } = useFeeCategory(params.id);
  const { mutateAsync: updateFeeCategory, error: updateError } = useUpdateFeeCategory(params.id);

  if (!isModuleEnabled('finance')) {
    return (
      <Container maxWidth="lg">
        <Box sx={{ py: 4 }}>
          <Alert severity="info">
            The Finance module is not enabled.
          </Alert>
        </Box>
      </Container>
    );
  }

  if (!can('finance.fees.manage')) {
    return (
      <Container maxWidth="lg">
        <Box sx={{ py: 4 }}>
          <Alert severity="error">
            You do not have permission to edit fee categories.
          </Alert>
        </Box>
      </Container>
    );
  }

  if (categoryLoading) {
    return (
      <Container maxWidth="lg">
        <Box sx={{ py: 4, display: 'flex', justifyContent: 'center' }}>
          <CircularProgress />
        </Box>
      </Container>
    );
  }

  if (categoryError || !feeCategory) {
    return (
      <Container maxWidth="lg">
        <Box sx={{ py: 4 }}>
          <Alert severity="error">
            Failed to load fee category: {categoryError?.message || 'Not found'}
          </Alert>
        </Box>
      </Container>
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
    <Container maxWidth="md">
      <Box sx={{ py: 4 }}>
        <Typography variant="h4" component="h1" gutterBottom>
          Edit Fee Category: {feeCategory.name}
        </Typography>

        <Box sx={{ mt: 3 }}>
          <FeeCategoryForm
            feeCategory={feeCategory}
            error={updateError?.message}
            onSubmit={handleSubmit}
            onCancel={() => router.back()}
          />
        </Box>
      </Box>
    </Container>
  );
}
