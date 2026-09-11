/**
 * Invoice detail page.
 */

'use client';

import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { Container, Box, Typography, Button, Grid, Paper, CircularProgress, Alert, Chip } from '@mui/material';
import { Edit as EditIcon, ArrowBack as BackIcon } from '@mui/icons-material';
import { useTenantStore } from '@/lib/tenant/store';
import { useInvoice } from '@/features/finance/hooks';

const statusColors = {
  draft: 'default',
  sent: 'info',
  paid: 'success',
  overdue: 'error',
} as const;

export default function InvoiceDetailPage({ params }: { params: { id: string } }) {
  const router = useRouter();
  const { can, isModuleEnabled, bootstrap } = useTenantStore();
  const { data: invoice, isLoading, error } = useInvoice(params.id);

  if (!bootstrap || !isModuleEnabled('finance') || !can('finance.invoices.view')) {
    return (
      <Container maxWidth="lg">
        <Box sx={{ py: 4 }}>
          <Alert severity="error">
            You do not have permission to view invoices.
          </Alert>
        </Box>
      </Container>
    );
  }

  if (isLoading) {
    return (
      <Container maxWidth="lg">
        <Box sx={{ py: 4, display: 'flex', justifyContent: 'center' }}>
          <CircularProgress />
        </Box>
      </Container>
    );
  }

  if (error || !invoice) {
    return (
      <Container maxWidth="lg">
        <Box sx={{ py: 4 }}>
          <Alert severity="error">
            Failed to load invoice: {error?.message || 'Not found'}
          </Alert>
        </Box>
      </Container>
    );
  }

  return (
    <Container maxWidth="lg">
      <Box sx={{ py: 4 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
            <Button startIcon={<BackIcon />} onClick={() => router.back()} variant="text" />
            <Typography variant="h4" component="h1">
              {invoice.invoice_number}
            </Typography>
          </Box>

          {can('finance.invoices.update') && (
            <Link href={`/dashboard/invoices/${invoice.id}/edit`} passHref legacyBehavior>
              <Button component="a" variant="contained" startIcon={<EditIcon />}>
                Edit
              </Button>
            </Link>
          )}
        </Box>

        <Grid container spacing={3}>
          <Grid item xs={12} md={6}>
            <Paper sx={{ p: 2 }}>
              <Typography variant="h6" gutterBottom>
                Invoice Details
              </Typography>
              <Box sx={{ display: 'grid', gridTemplateColumns: '150px 1fr', gap: 1 }}>
                <Typography variant="body2" color="textSecondary">
                  Invoice #:
                </Typography>
                <Typography variant="body2">{invoice.invoice_number}</Typography>

                <Typography variant="body2" color="textSecondary">
                  Student:
                </Typography>
                <Typography variant="body2">{invoice.student_name}</Typography>

                <Typography variant="body2" color="textSecondary">
                  Amount:
                </Typography>
                <Typography variant="body2" sx={{ fontWeight: 600, color: '#2e7d32' }}>
                  ${invoice.amount.toFixed(2)}
                </Typography>

                <Typography variant="body2" color="textSecondary">
                  Due Date:
                </Typography>
                <Typography variant="body2">{invoice.due_date}</Typography>

                <Typography variant="body2" color="textSecondary">
                  Status:
                </Typography>
                <Box>
                  <Chip label={invoice.status} color={statusColors[invoice.status as keyof typeof statusColors]} size="small" />
                </Box>
              </Box>
            </Paper>
          </Grid>

          <Grid item xs={12} md={6}>
            <Paper sx={{ p: 2 }}>
              <Typography variant="h6" gutterBottom>
                Payment Information
              </Typography>
              <Box sx={{ display: 'grid', gridTemplateColumns: '150px 1fr', gap: 1 }}>
                <Typography variant="body2" color="textSecondary">
                  Is Paid:
                </Typography>
                <Typography variant="body2">
                  {invoice.is_paid ? '✓ Yes' : 'No'}
                </Typography>

                {invoice.paid_date && (
                  <>
                    <Typography variant="body2" color="textSecondary">
                      Paid Date:
                    </Typography>
                    <Typography variant="body2">{invoice.paid_date}</Typography>
                  </>
                )}

                <Typography variant="body2" color="textSecondary">
                  Created:
                </Typography>
                <Typography variant="body2">
                  {new Date(invoice.created_at).toLocaleDateString()}
                </Typography>
              </Box>
            </Paper>
          </Grid>
        </Grid>
      </Box>
    </Container>
  );
}
