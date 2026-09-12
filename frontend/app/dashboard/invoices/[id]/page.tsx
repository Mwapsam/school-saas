/**
 * Invoice detail page.
 *
 * Shows the guardian's consolidated invoice for an academic year: totals,
 * status, and every child's billed line item. Entirely read-only — there is
 * no edit or mark-paid action (see features/finance/hooks.ts).
 */

'use client';

export const dynamic = 'force-dynamic';

import { useRouter } from 'next/navigation';
import {
  Container,
  Box,
  Typography,
  Button,
  Grid,
  Paper,
  CircularProgress,
  Alert,
  Chip,
  Table,
  TableHead,
  TableBody,
  TableRow,
  TableCell,
} from '@mui/material';
import { ArrowBack as BackIcon, PictureAsPdf as PdfIcon } from '@mui/icons-material';
import { useTenantStore } from '@/lib/tenant/store';
import { useInvoice, getInvoicePdfUrl } from '@/features/finance/hooks';

const statusColors = {
  open: 'info',
  paid: 'success',
  void: 'default',
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

          <Button
            component="a"
            href={getInvoicePdfUrl(invoice.id)}
            target="_blank"
            rel="noopener noreferrer"
            variant="outlined"
            startIcon={<PdfIcon />}
          >
            Download PDF
          </Button>
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
                  Guardian:
                </Typography>
                <Typography variant="body2">{invoice.guardian_name}</Typography>

                <Typography variant="body2" color="textSecondary">
                  Academic Year:
                </Typography>
                <Typography variant="body2">{invoice.academic_year_label}</Typography>

                <Typography variant="body2" color="textSecondary">
                  Due Date:
                </Typography>
                <Typography variant="body2">{invoice.due_date || '—'}</Typography>

                <Typography variant="body2" color="textSecondary">
                  Status:
                </Typography>
                <Box>
                  <Chip label={invoice.status} color={statusColors[invoice.status]} size="small" />
                </Box>
              </Box>
            </Paper>
          </Grid>

          <Grid item xs={12} md={6}>
            <Paper sx={{ p: 2 }}>
              <Typography variant="h6" gutterBottom>
                Amounts
              </Typography>
              <Box sx={{ display: 'grid', gridTemplateColumns: '150px 1fr', gap: 1 }}>
                <Typography variant="body2" color="textSecondary">
                  Subtotal:
                </Typography>
                <Typography variant="body2">${Number(invoice.subtotal).toFixed(2)}</Typography>

                <Typography variant="body2" color="textSecondary">
                  Amount Paid:
                </Typography>
                <Typography variant="body2">${Number(invoice.amount_paid).toFixed(2)}</Typography>

                <Typography variant="body2" color="textSecondary">
                  Balance Due:
                </Typography>
                <Typography variant="body2" sx={{ fontWeight: 600, color: invoice.balance_due > 0 ? '#c62828' : '#2e7d32' }}>
                  ${Number(invoice.balance_due).toFixed(2)}
                </Typography>

                <Typography variant="body2" color="textSecondary">
                  Generated:
                </Typography>
                <Typography variant="body2">
                  {new Date(invoice.generated_at).toLocaleDateString()}
                </Typography>

                <Typography variant="body2" color="textSecondary">
                  Last Updated:
                </Typography>
                <Typography variant="body2">
                  {new Date(invoice.last_updated_at).toLocaleDateString()}
                </Typography>
              </Box>
            </Paper>
          </Grid>

          <Grid item xs={12}>
            <Paper sx={{ p: 2 }}>
              <Typography variant="h6" gutterBottom>
                Billed Items
              </Typography>
              {invoice.lines.length === 0 ? (
                <Typography variant="body2" color="textSecondary">
                  No line items on this invoice.
                </Typography>
              ) : (
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>Student</TableCell>
                      <TableCell>Description</TableCell>
                      <TableCell align="right">Amount</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {invoice.lines.map((line) => (
                      <TableRow key={line.id}>
                        <TableCell>{line.student_name}</TableCell>
                        <TableCell>{line.description}</TableCell>
                        <TableCell align="right">${Number(line.amount).toFixed(2)}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </Paper>
          </Grid>
        </Grid>
      </Box>
    </Container>
  );
}
