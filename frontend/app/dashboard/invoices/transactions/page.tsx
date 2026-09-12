/**
 * Transactions list page (read-only).
 */

'use client';

export const dynamic = 'force-dynamic';

import { Container, Box, Typography, Alert } from '@mui/material';
import type { GridColDef } from '@mui/x-data-grid';
import { useTenantStore } from '@/lib/tenant/store';
import { useTransactionList, type Transaction } from '@/features/finance/hooks';
import { useServerTable } from '@/hooks/useServerTable';
import { DataTable } from '@/components/data-table/DataTable';

export default function TransactionsPage() {
  const { can, isModuleEnabled, bootstrap } = useTenantStore();
  const table = useServerTable();
  const { data, error, isLoading, refetch } = useTransactionList({
    page: table.queryParams.page,
    page_size: table.queryParams.page_size,
    search: table.queryParams.search,
    ordering: table.queryParams.ordering,
  });

  if (!bootstrap || !isModuleEnabled('finance') || !can('finance.transactions.view')) {
    return (
      <Container maxWidth="lg">
        <Box sx={{ py: 4 }}>
          <Alert severity="error">You do not have permission to view transactions.</Alert>
        </Box>
      </Container>
    );
  }

  const columns: GridColDef<Transaction>[] = [
    { field: 'reference', headerName: 'Reference', flex: 1 },
    { field: 'type', headerName: 'Type', flex: 0.8 },
    { field: 'amount', headerName: 'Amount', flex: 0.8 },
    { field: 'date', headerName: 'Date', flex: 1 },
    { field: 'notes', headerName: 'Notes', flex: 1.2 },
  ];

  return (
    <Container maxWidth="lg">
      <Box sx={{ py: 4 }}>
        <Typography variant="h4" component="h1" gutterBottom>
          Transactions
        </Typography>

        <DataTable<Transaction>
          rows={data?.results ?? []}
          columns={columns}
          rowCount={(data as any)?.count ?? data?.results?.length ?? 0}
          loading={isLoading}
          error={error as Error | null}
          onRetry={() => refetch()}
          paginationModel={table.paginationModel}
          onPaginationModelChange={table.onPaginationModelChange}
          search={table.search}
          onSearchChange={table.onSearchChange}
          searchPlaceholder="Search transactions..."
          emptyMessage="No transactions found"
        />
      </Box>
    </Container>
  );
}
