/**
 * Attendance list page (read-only).
 */

'use client';

export const dynamic = 'force-dynamic';

import { Container, Box, Typography, Alert } from '@mui/material';
import type { GridColDef } from '@mui/x-data-grid';
import { useTenantStore } from '@/lib/tenant/store';
import { useAttendanceList, type AttendanceRecord } from '@/features/hr/hooks';
import { useServerTable } from '@/hooks/useServerTable';
import { DataTable } from '@/components/data-table/DataTable';

export default function AttendancePage() {
  const { can, isModuleEnabled, bootstrap } = useTenantStore();
  const table = useServerTable();
  const { data, error, isLoading, refetch } = useAttendanceList({
    page: table.queryParams.page,
    page_size: table.queryParams.page_size,
    search: table.queryParams.search,
    ordering: table.queryParams.ordering,
  });

  if (!bootstrap || !isModuleEnabled('hr') || !can('hr.attendance.view')) {
    return (
      <Container maxWidth="lg">
        <Box sx={{ py: 4 }}>
          <Alert severity="error">You do not have permission to view attendance.</Alert>
        </Box>
      </Container>
    );
  }

  const columns: GridColDef<AttendanceRecord>[] = [
    { field: 'employee_name', headerName: 'Employee', flex: 1.2 },
    { field: 'date', headerName: 'Date', flex: 1 },
    { field: 'status', headerName: 'Status', flex: 0.8 },
    { field: 'notes', headerName: 'Notes', flex: 1.2 },
  ];

  return (
    <Container maxWidth="lg">
      <Box sx={{ py: 4 }}>
        <Typography variant="h4" component="h1" gutterBottom>
          Attendance
        </Typography>

        <DataTable<AttendanceRecord>
          rows={data?.results ?? []}
          columns={columns}
          rowCount={data?.count ?? 0}
          loading={isLoading}
          error={error as Error | null}
          onRetry={() => refetch()}
          paginationModel={table.paginationModel}
          onPaginationModelChange={table.onPaginationModelChange}
          search={table.search}
          onSearchChange={table.onSearchChange}
          searchPlaceholder="Search attendance..."
          emptyMessage="No attendance records found"
        />
      </Box>
    </Container>
  );
}
