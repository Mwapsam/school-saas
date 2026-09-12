/**
 * Create new fee category page.
 */

'use client';

export const dynamic = 'force-dynamic';

import { useRouter } from 'next/navigation';
import { Container, Box, Typography, Alert } from '@mui/material';
import { useTenantStore } from '@/lib/tenant/store';
import { useCreateFeeCategory } from '@/features/finance/hooks';
import { FeeCategoryForm } from '@/features/finance/components/FeeCategoryForm';

export default function CreateFeeCategoryPage() {
  const router = useRouter();
  const { can, isModuleEnabled } = useTenantStore();
  const { mutateAsync: createFeeCategory, error } = useCreateFeeCategory();

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
            You do not have permission to create fee categories.
          </Alert>
        </Box>
      </Container>
    );
  }

  const handleSubmit = async (data: any) => {
    try {
      await createFeeCategory(data);
      router.push('/dashboard/invoices/fee-categories');
    } catch (err) {
      console.error('Create failed:', err);
      throw err;
    }
  };

  return (
    <Container maxWidth="md">
      <Box sx={{ py: 4 }}>
        <Typography variant="h4" component="h1" gutterBottom>
          Create New Fee Category
        </Typography>

        <Box sx={{ mt: 3 }}>
          <FeeCategoryForm
            error={error?.message}
            onSubmit={handleSubmit}
            onCancel={() => router.back()}
          />
        </Box>
      </Box>
    </Container>
  );
}
