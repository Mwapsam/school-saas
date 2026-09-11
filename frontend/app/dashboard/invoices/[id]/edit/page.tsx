/**
 * Edit invoice page.
 */

'use client';

export const dynamic = 'force-dynamic';

import { useRouter } from 'next/navigation';
import { Container, Box, Typography, Alert, CircularProgress } from '@mui/material';
import { useTenantStore } from '@/lib/tenant/store';
import { useInvoice, useUpdateInvoice } from '@/features/finance/hooks';
import { InvoiceForm } from '@/features/finance/InvoiceForm';

export default function EditInvoicePage({ params }: { params: { id: string } }) {
  const router = useRouter();
  const { can, isModuleEnabled, bootstrap } = useTenantStore();
  const { data: invoice, isLoading: invoiceLoading, error: invoiceError } = useInvoice(params.id);
  const { mutateAsync: updateInvoice, error: updateError } = useUpdateInvoice(params.id);

  if (!bootstrap || !isModuleEnabled('finance') || !can('finance.invoices.update')) {
    return (
      <Container maxWidth="lg">
        <Box sx={{ py: 4 }}>
          <Alert severity="error">
            You do not have permission to edit invoices.
          </Alert>
        </Box>
      </Container>
    );
  }

  if (invoiceLoading) {
    return (
      <Container maxWidth="lg">
        <Box sx={{ py: 4, display: 'flex', justifyContent: 'center' }}>
          <CircularProgress />
        </Box>
      </Container>
    );
  }

  if (invoiceError || !invoice) {
    return (
      <Container maxWidth="lg">
        <Box sx={{ py: 4 }}>
          <Alert severity="error">
            Failed to load invoice
          </Alert>
        </Box>
      </Container>
    );
  }

  const handleSubmit = async (data: any) => {
    try {
      await updateInvoice(data);
      router.push(`/dashboard/invoices/${invoice.id}`);
    } catch (err) {
      console.error('Update failed:', err);
      throw err;
    }
  };

  return (
    <Container maxWidth="md">
      <Box sx={{ py: 4 }}>
        <Typography variant="h4" component="h1" gutterBottom>
          Edit Invoice: {invoice.invoice_number}
        </Typography>

        <Box sx={{ mt: 3 }}>
          <InvoiceForm
            invoice={invoice}
            error={updateError?.message}
            onSubmit={handleSubmit}
            onCancel={() => router.back()}
          />
        </Box>
      </Box>
    </Container>
  );
}
