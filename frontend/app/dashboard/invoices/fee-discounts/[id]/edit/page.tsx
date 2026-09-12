/**
 * Edit fee discount page.
 */

'use client';

export const dynamic = 'force-dynamic';

import { useRouter } from 'next/navigation';
import { Container, Box, Typography, Alert, CircularProgress } from '@mui/material';
import { useTenantStore } from '@/lib/tenant/store';
import { useFeeDiscount, useUpdateFeeDiscount } from '@/features/finance/hooks';
import { FeeDiscountForm } from '@/features/finance/components/FeeDiscountForm';

export default function EditFeeDiscountPage({ params }: { params: { id: string } }) {
  const router = useRouter();
  const { can, isModuleEnabled } = useTenantStore();
  const { data: feeDiscount, isLoading: discountLoading, error: discountError } = useFeeDiscount(params.id);
  const { mutateAsync: updateFeeDiscount, error: updateError } = useUpdateFeeDiscount(params.id);

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

  if (!can('finance.discounts.manage')) {
    return (
      <Container maxWidth="lg">
        <Box sx={{ py: 4 }}>
          <Alert severity="error">
            You do not have permission to edit fee discounts.
          </Alert>
        </Box>
      </Container>
    );
  }

  if (discountLoading) {
    return (
      <Container maxWidth="lg">
        <Box sx={{ py: 4, display: 'flex', justifyContent: 'center' }}>
          <CircularProgress />
        </Box>
      </Container>
    );
  }

  if (discountError || !feeDiscount) {
    return (
      <Container maxWidth="lg">
        <Box sx={{ py: 4 }}>
          <Alert severity="error">
            Failed to load fee discount: {discountError?.message || 'Not found'}
          </Alert>
        </Box>
      </Container>
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
    <Container maxWidth="md">
      <Box sx={{ py: 4 }}>
        <Typography variant="h4" component="h1" gutterBottom>
          Edit Fee Discount: {feeDiscount.name}
        </Typography>

        <Box sx={{ mt: 3 }}>
          <FeeDiscountForm
            feeDiscount={feeDiscount}
            error={updateError?.message}
            onSubmit={handleSubmit}
            onCancel={() => router.back()}
          />
        </Box>
      </Box>
    </Container>
  );
}
