/**
 * Invoices list page.
 */

'use client';

export const dynamic = 'force-dynamic';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { Container, Box, Typography, Button, Alert, Chip, IconButton } from '@mui/material';
import {
  Add as AddIcon,
  Edit as EditIcon,
  Delete as DeleteIcon,
  Visibility as ViewIcon,
  Paid as PaidIcon,
} from '@mui/icons-material';
import type { GridColDef } from '@mui/x-data-grid';
import { useTenantStore } from '@/lib/tenant/store';
import { useInvoiceList, useDeleteInvoice, useMarkInvoicePaid, Invoice } from '@/features/finance/hooks';
import { useServerTable } from '@/hooks/useServerTable';
import { DataTable } from '@/components/data-table/DataTable';
import { useState } from 'react';

const statusColors: Record<string, 'default' | 'primary' | 'secondary' | 'error' | 'info' | 'success' | 'warning'> = {
  draft: 'default',
  sent: 'info',
  paid: 'success',
  overdue: 'error',
};

export default function InvoicesPage() {
  const router = useRouter();
  const { can, isModuleEnabled } = useTenantStore();

  const table = useServerTable({ initialOrdering: '-created_at' });
  const { data, isLoading, error, refetch } = useInvoiceList(table.queryParams);
  const deleteInvoice = useDeleteInvoice();

  // useMarkInvoicePaid requires an id at hook-call time; track which invoice
  // is targeted and call the hook with that id, mirroring the rules-of-hooks
  // pattern used for delete (mutate at click time, hook stays stable).
  const [markPaidTargetId, setMarkPaidTargetId] = useState<string | null>(null);
  const markInvoicePaid = useMarkInvoicePaid(markPaidTargetId || '');

  const canEdit = can('finance.invoices.update');
  const canDelete = can('finance.invoices.delete');
  const canMarkPaid = can('finance.invoices.update');

  const handleDeleteInvoice = async (id: string, invoiceNumber: string) => {
    if (!window.confirm(`Delete invoice ${invoiceNumber}?`)) return;
    try {
      await deleteInvoice.mutateAsync(id);
      router.refresh();
    } catch (err) {
      console.error('Delete failed:', err);
    }
  };

  const handleMarkPaid = async (id: string) => {
    setMarkPaidTargetId(id);
    try {
      await markInvoicePaid.mutateAsync();
    } catch (err) {
      console.error('Mark paid failed:', err);
    }
  };

  if (!isModuleEnabled('finance')) {
    return (
      <Container maxWidth="lg">
        <Box sx={{ py: 4 }}>
          <Alert severity="info">
            The Finance module is not enabled. Contact your administrator.
          </Alert>
        </Box>
      </Container>
    );
  }

  if (!can('finance.invoices.view')) {
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

  const columns: GridColDef<Invoice>[] = [
    { field: 'invoice_number', headerName: 'Invoice #', flex: 1, minWidth: 130 },
    { field: 'student_name', headerName: 'Student', flex: 1.5, minWidth: 160 },
    {
      field: 'amount',
      headerName: 'Amount',
      flex: 1,
      minWidth: 110,
      valueGetter: (params) => `$${params.row.amount.toFixed(2)}`,
    },
    { field: 'due_date', headerName: 'Due Date', flex: 1, minWidth: 120 },
    {
      field: 'status',
      headerName: 'Status',
      flex: 1,
      minWidth: 110,
      sortable: false,
      renderCell: (params) => (
        <Chip label={params.row.status} color={statusColors[params.row.status]} size="small" />
      ),
    },
    {
      field: 'actions',
      headerName: 'Actions',
      flex: 1.3,
      minWidth: 170,
      sortable: false,
      filterable: false,
      align: 'right',
      headerAlign: 'right',
      renderCell: (params) => (
        <Box>
          <Link href={`/dashboard/invoices/${params.row.id}`} passHref legacyBehavior>
            <IconButton size="small" component="a" title="View">
              <ViewIcon fontSize="small" />
            </IconButton>
          </Link>
          {canEdit && (
            <Link href={`/dashboard/invoices/${params.row.id}/edit`} passHref legacyBehavior>
              <IconButton size="small" component="a" title="Edit">
                <EditIcon fontSize="small" />
              </IconButton>
            </Link>
          )}
          {canMarkPaid && params.row.status !== 'paid' && (
            <IconButton
              size="small"
              title="Mark Paid"
              onClick={() => handleMarkPaid(params.row.id)}
            >
              <PaidIcon fontSize="small" color="success" />
            </IconButton>
          )}
          {canDelete && (
            <IconButton
              size="small"
              title="Delete"
              onClick={() => handleDeleteInvoice(params.row.id, params.row.invoice_number)}
            >
              <DeleteIcon fontSize="small" color="error" />
            </IconButton>
          )}
        </Box>
      ),
    },
  ];

  return (
    <Container maxWidth="lg">
      <Box sx={{ py: 4 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
          <Typography variant="h4" component="h1">
            Invoices
          </Typography>
          {can('finance.invoices.create') && (
            <Link href="/dashboard/invoices/create" passHref legacyBehavior>
              <Button component="a" variant="contained" startIcon={<AddIcon />}>
                New Invoice
              </Button>
            </Link>
          )}
        </Box>

        <DataTable<Invoice>
          rows={data?.results || []}
          columns={columns}
          rowCount={data?.count || 0}
          loading={isLoading}
          error={error as Error | null}
          onRetry={() => refetch()}
          paginationModel={table.paginationModel}
          onPaginationModelChange={table.onPaginationModelChange}
          onSortModelChange={(model) =>
            table.onSortModelChange(model.map((m) => ({ field: m.field, sort: m.sort ?? null })))
          }
          search={table.search}
          onSearchChange={table.onSearchChange}
          searchPlaceholder="Search by student name or invoice number"
          emptyMessage="No invoices found"
        />
      </Box>
    </Container>
  );
}
