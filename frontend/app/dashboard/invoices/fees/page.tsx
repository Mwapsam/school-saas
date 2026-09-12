/**
 * Student Fees list page (read-only).
 */

'use client';

export const dynamic = 'force-dynamic';

import { Container, Box, Typography, Alert } from '@mui/material';
import type { GridColDef } from '@mui/x-data-grid';
import { useTenantStore } from '@/lib/tenant/store';
import { useStudentFeeList, type StudentFee } from '@/features/finance/hooks';
import { useServerTable } from '@/hooks/useServerTable';
import { DataTable } from '@/components/data-table/DataTable';

export default function FeesPage() {
  const { can, isModuleEnabled, bootstrap } = useTenantStore();
  const table = useServerTable();
  const { data, error, isLoading, refetch } = useStudentFeeList({
    page: table.queryParams.page,
    page_size: table.queryParams.page_size,
    search: table.queryParams.search,
    ordering: table.queryParams.ordering,
  });

  if (!bootstrap || !isModuleEnabled('finance') || !can('finance.fees.view')) {
    return (
      <Container maxWidth="lg">
        <Box sx={{ py: 4 }}>
          <Alert severity="error">You do not have permission to view fees.</Alert>
        </Box>
      </Container>
    );
  }

  const columns: GridColDef<StudentFee>[] = [
    { field: 'student_name', headerName: 'Student', flex: 1.2 },
    { field: 'fee_category_name', headerName: 'Fee Category', flex: 1 },
    { field: 'balance', headerName: 'Balance', flex: 0.8 },
    {
      field: 'is_paid',
      headerName: 'Status',
      flex: 0.6,
      valueFormatter: (value: boolean) => (value ? 'Paid' : 'Unpaid'),
    },
    { field: 'transaction_date', headerName: 'Date', flex: 0.8 },
  ];

  return (
    <Container maxWidth="lg">
      <Box sx={{ py: 4 }}>
        <Typography variant="h4" component="h1" gutterBottom>
          Fees
        </Typography>

        <DataTable<StudentFee>
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
          searchPlaceholder="Search fees..."
          emptyMessage="No fee records found"
        />
      </Box>
    </Container>
  );
}
