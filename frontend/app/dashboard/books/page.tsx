/**
 * Library books list page.
 */

'use client';

export const dynamic = 'force-dynamic';

import { Container, Box, Typography, Alert } from '@mui/material';
import type { GridColDef } from '@mui/x-data-grid';
import { useTenantStore } from '@/lib/tenant/store';
import { useLibraryBookList, type LibraryBook } from '@/features/library/hooks';
import { useServerTable } from '@/hooks/useServerTable';
import { DataTable } from '@/components/data-table/DataTable';

export default function BooksPage() {
  const { can, isModuleEnabled, bootstrap } = useTenantStore();
  const table = useServerTable();
  const { data, error, isLoading, refetch } = useLibraryBookList({
    page: table.queryParams.page,
    page_size: table.queryParams.page_size,
    search: table.queryParams.search,
  });

  if (!bootstrap || !isModuleEnabled('library') || !can('library.view')) {
    return (
      <Container maxWidth="lg">
        <Box sx={{ py: 4 }}>
          <Alert severity="error">You do not have permission to view library books.</Alert>
        </Box>
      </Container>
    );
  }

  const columns: GridColDef<LibraryBook>[] = [
    { field: 'title', headerName: 'Title', flex: 1.5 },
    { field: 'author', headerName: 'Author', flex: 1 },
    { field: 'isbn', headerName: 'ISBN', flex: 1 },
    { field: 'category_name', headerName: 'Category', flex: 1 },
    {
      field: 'available_copies',
      headerName: 'Available',
      flex: 1,
      sortable: false,
      valueGetter: (params) => `${params.row.available_copies} / ${params.row.total_copies}`,
    },
  ];

  return (
    <Container maxWidth="lg">
      <Box sx={{ py: 4 }}>
        <Typography variant="h4" component="h1" gutterBottom>
          Library Books
        </Typography>

        <DataTable<LibraryBook>
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
          searchPlaceholder="Search books..."
          emptyMessage="No books found"
        />
      </Box>
    </Container>
  );
}
