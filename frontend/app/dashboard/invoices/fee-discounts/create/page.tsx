/**
 * Create new fee discount page.
 */

'use client';

export const dynamic = 'force-dynamic';

import { useRouter } from 'next/navigation';
import { Container, Box, Typography, Alert } from '@mui/material';
import { useTenantStore } from '@/lib/tenant/store';
import { useCreateFeeDiscount } from '@/features/finance/hooks';
import { FeeDiscountForm } from '@/features/finance/components/FeeDiscountForm';

export default function CreateFeeDiscountPage() {
  const router = useRouter();
  const { can, isModuleEnabled } = useTenantStore();
  const { mutateAsync: createFeeDiscount, error } = useCreateFeeDiscount();

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
            You do not have permission to create fee discounts.
          </Alert>
        </Box>
      </Container>
    );
  }

  const handleSubmit = async (data: any) => {
    try {
      await createFeeDiscount(data);
      router.push('/dashboard/invoices/fee-discounts');
    } catch (err) {
      console.error('Create failed:', err);
      throw err;
    }
  };

  return (
    <Container maxWidth="md">
      <Box sx={{ py: 4 }}>
        <Typography variant="h4" component="h1" gutterBottom>
          Create New Fee Discount
        </Typography>

        <Box sx={{ mt: 3 }}>
          <FeeDiscountForm
            error={error?.message}
            onSubmit={handleSubmit}
            onCancel={() => router.back()}
          />
        </Box>
      </Box>
    </Container>
  );
}
