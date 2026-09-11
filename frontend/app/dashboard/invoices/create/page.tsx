/**
 * Create new invoice page.
 */

'use client';

import { useRouter } from 'next/navigation';
import { Container, Box, Typography, Alert } from '@mui/material';
import { useTenantStore } from '@/lib/tenant/store';
import { useCreateInvoice } from '@/features/finance/hooks';
import { InvoiceForm } from '@/features/finance/InvoiceForm';

export default function CreateInvoicePage() {
  const router = useRouter();
  const { can, isModuleEnabled, bootstrap } = useTenantStore();
  const { mutateAsync: createInvoice, error } = useCreateInvoice();

  if (!bootstrap || !isModuleEnabled('finance') || !can('finance.invoices.create')) {
    return (
      <Container maxWidth="lg">
        <Box sx={{ py: 4 }}>
          <Alert severity="error">
            You do not have permission to create invoices.
          </Alert>
        </Box>
      </Container>
    );
  }

  const handleSubmit = async (data: any) => {
    try {
      await createInvoice(data);
      router.push('/dashboard/invoices');
    } catch (err) {
      console.error('Create failed:', err);
      throw err;
    }
  };

  return (
    <Container maxWidth="md">
      <Box sx={{ py: 4 }}>
        <Typography variant="h4" component="h1" gutterBottom>
          Create New Invoice
        </Typography>

        <Box sx={{ mt: 3 }}>
          <InvoiceForm
            error={error?.message}
            onSubmit={handleSubmit}
            onCancel={() => router.back()}
          />
        </Box>
      </Box>
    </Container>
  );
}
