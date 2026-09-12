/**
 * Invoice detail page using design system components.
 */

'use client';

export const dynamic = 'force-dynamic';

import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { Button, Grid, Table, TableHead, TableBody, TableRow, TableCell, Typography, Box, Alert, TableContainer, useTheme } from '@mui/material';
import { ChevronLeft as BackIcon, PictureAsPdf as PdfIcon } from '@mui/icons-material';
import { useTenantStore } from '@/lib/tenant/store';
import { useInvoice, getInvoicePdfUrl } from '@/features/finance/hooks';
import { Page } from '@/components/page/Page';
import { PageHeader } from '@/components/page/PageHeader';
import { PageContent } from '@/components/page/PageContent';
import { SectionCard, DetailField } from '@/components/page';
import { LoadingState } from '@/components/feedback/LoadingState';
import { ErrorState } from '@/components/feedback/ErrorState';
import { EmptyState } from '@/components/feedback/EmptyState';
import { StatusBadge } from '@/components/data/StatusBadge';

export default function InvoiceDetailPage({ params }: { params: { id: string } }) {
  const router = useRouter();
  const theme = useTheme();
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
            <SectionCard title="Invoice Details">
              <DetailField label="Invoice #" value={invoice.invoice_number} />
              <DetailField label="Guardian" value={invoice.guardian_name} truncate />
              <DetailField label="Academic Year" value={invoice.academic_year_label} />
              <DetailField label="Due Date" value={invoice.due_date || '—'} />
              <DetailField
                label="Status"
                value={
                  <StatusBadge label={invoice.status} status={invoice.status} />
                }
              />
            </SectionCard>
          </Grid>

          <Grid item xs={12} md={6}>
            <SectionCard title="Amounts">
              <DetailField label="Subtotal" value={`$${Number(invoice.subtotal).toFixed(2)}`} />
              <DetailField label="Amount Paid" value={`$${Number(invoice.amount_paid).toFixed(2)}`} />
              <DetailField
                label="Balance Due"
                value={
                  <Typography
                    variant="body2"
                    sx={{
                      fontWeight: 600,
                      color: invoice.balance_due > 0 ? theme.palette.error.main : theme.palette.success.main,
                    }}
                  >
                    ${Number(invoice.balance_due).toFixed(2)}
                  </Typography>
                }
              />
              <DetailField label="Generated" value={new Date(invoice.generated_at).toLocaleDateString()} />
              <DetailField label="Last Updated" value={new Date(invoice.last_updated_at).toLocaleDateString()} />
            </SectionCard>
          </Grid>

          <Grid item xs={12}>
            <SectionCard title="Billed Items">
              {invoice.lines.length === 0 ? (
                <EmptyState message="No line items on this invoice." />
              ) : (
                <TableContainer>
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
                </TableContainer>
              )}
            </SectionCard>
          </Grid>
        </Grid>
      </PageContent>
    </Page>
  );
}
