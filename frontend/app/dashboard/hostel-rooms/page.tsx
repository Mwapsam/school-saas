/**
 * Hostel rooms list page.
 */

'use client';

export const dynamic = 'force-dynamic';

import { Container, Box, Typography, Alert } from '@mui/material';
import type { GridColDef } from '@mui/x-data-grid';
import { useTenantStore } from '@/lib/tenant/store';
import { useHostelRoomList, type HostelRoom } from '@/features/hostel/hooks';
import { useServerTable } from '@/hooks/useServerTable';
import { DataTable } from '@/components/data-table/DataTable';

export default function HostelRoomsPage() {
  const { can, isModuleEnabled, bootstrap } = useTenantStore();
  const table = useServerTable();
  const { data, error, isLoading, refetch } = useHostelRoomList({
    page: table.queryParams.page,
    page_size: table.queryParams.page_size,
    search: table.queryParams.search,
  });

  if (!bootstrap || !isModuleEnabled('hostel') || !can('hostel.rooms.view')) {
    return (
      <Container maxWidth="lg">
        <Box sx={{ py: 4 }}>
          <Alert severity="error">You do not have permission to view hostel.</Alert>
        </Box>
      </Container>
    );
  }

  const columns: GridColDef<HostelRoom>[] = [
    { field: 'hostel_name', headerName: 'Hostel', flex: 1 },
    { field: 'room_number', headerName: 'Room Number', flex: 1 },
    { field: 'capacity', headerName: 'Capacity', flex: 0.8 },
    {
      field: 'current_occupancy',
      headerName: 'Occupancy',
      flex: 1,
      sortable: false,
      valueGetter: (params) => `${params.row.current_occupancy} / ${params.row.capacity}`,
    },
  ];

  return (
    <Container maxWidth="lg">
      <Box sx={{ py: 4 }}>
        <Typography variant="h4" component="h1" gutterBottom>
          Hostel Rooms
        </Typography>

        <DataTable<HostelRoom>
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
          searchPlaceholder="Search rooms..."
          emptyMessage="No rooms found"
        />
      </Box>
    </Container>
  );
}
