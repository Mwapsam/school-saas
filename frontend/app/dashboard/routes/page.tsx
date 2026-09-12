/**
 * Transport routes list page.
 */

'use client';

export const dynamic = 'force-dynamic';

import { Container, Box, Typography, Alert } from '@mui/material';
import type { GridColDef } from '@mui/x-data-grid';
import { useTenantStore } from '@/lib/tenant/store';
import { useTransportRouteList, type TransportRoute } from '@/features/transport/hooks';
import { useServerTable } from '@/hooks/useServerTable';
import { DataTable } from '@/components/data-table/DataTable';

export default function RoutesPage() {
  const { can, isModuleEnabled, bootstrap } = useTenantStore();
  const table = useServerTable();
  const { data, error, isLoading, refetch } = useTransportRouteList({
    page: table.queryParams.page,
    page_size: table.queryParams.page_size,
    search: table.queryParams.search,
  });

  if (!bootstrap || !isModuleEnabled('transport') || !can('transport.routes.view')) {
    return (
      <Container maxWidth="lg">
        <Box sx={{ py: 4 }}>
          <Alert severity="error">You do not have permission to view transport routes.</Alert>
        </Box>
      </Container>
    );
  }

  const columns: GridColDef<TransportRoute>[] = [
    { field: 'name', headerName: 'Route Name', flex: 1.5 },
    { field: 'code', headerName: 'Code', flex: 1 },
    { field: 'route_type', headerName: 'Type', flex: 1 },
    { field: 'vehicle_name', headerName: 'Vehicle', flex: 1 },
    { field: 'student_count', headerName: 'Students', flex: 0.8 },
  ];

  return (
    <Container maxWidth="lg">
      <Box sx={{ py: 4 }}>
        <Typography variant="h4" component="h1" gutterBottom>
          Transport Routes
        </Typography>

        <DataTable<TransportRoute>
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
          searchPlaceholder="Search routes..."
          emptyMessage="No routes found"
        />
      </Box>
    </Container>
  );
}
