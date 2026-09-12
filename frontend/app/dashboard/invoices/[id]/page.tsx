/**
 * Invoice detail page using design system components.
 */

'use client';

export const dynamic = 'force-dynamic';

import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { Button, Grid, Paper, Table, TableHead, TableBody, TableRow, TableCell, Typography, Box, Alert } from '@mui/material';
import { ChevronLeft as BackIcon, PictureAsPdf as PdfIcon } from '@mui/icons-material';
import { useTenantStore } from '@/lib/tenant/store';
import { useInvoice, getInvoicePdfUrl } from '@/features/finance/hooks';
import { Page } from '@/components/page/Page';
import { PageHeader } from '@/components/page/PageHeader';
import { PageContent } from '@/components/page/PageContent';
import { LoadingState } from '@/components/feedback/LoadingState';
import { ErrorState } from '@/components/feedback/ErrorState';
import { StatusBadge } from '@/components/data/StatusBadge';

export default function InvoiceDetailPage({ params }: { params: { id: string } }) {
  const router = useRouter();
  const { can, isModuleEnabled, bootstrap } = useTenantStore();
  const { data: invoice, isLoading, error, refetch } = useInvoice(params.id);

  if (!bootstrap || !isModuleEnabled('finance') || !can('finance.invoices.view')) {
    return (
      <Page>
        <Alert severity="error">You do not have permission to view invoices.</Alert>
      </Page>
    );
  }

  if (isLoading) {
    return (
      <Page>
        <LoadingState />
      </Page>
    );
  }

  if (error || !invoice) {
    return (
      <Page>
        <ErrorState error={error} onRetry={() => refetch()} />
      </Page>
    );
  }

  return (
    <Page>
      <PageHeader
        title={invoice.invoice_number}
        description={`Guardian: ${invoice.guardian_name}`}
        breadcrumbs={
          <Link href="/dashboard/invoices" passHref legacyBehavior>
            <Button startIcon={<BackIcon />} variant="text">
              Back to Invoices
            </Button>
          </Link>
        }
        actions={
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
        }
      />

      <PageContent>
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
                  <StatusBadge status={invoice.status} />
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
      </PageContent>
    </Page>
  );
}
