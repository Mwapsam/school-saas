/**
 * Library books list page.
 *
 * Uses design system components:
 * - Page wrapper for consistent layout
 * - PageHeader for title
 * - DataTable for books list
 */

'use client';

export const dynamic = 'force-dynamic';

import { Alert } from '@mui/material';
import type { GridColDef } from '@mui/x-data-grid';
import { useTenantStore } from '@/lib/tenant/store';
import { useLibraryBookList, type LibraryBook } from '@/features/library/hooks';
import { useServerTable } from '@/hooks/useServerTable';
import { DataTable } from '@/components/data-table/DataTable';
import { Page } from '@/components/page/Page';
import { PageHeader } from '@/components/page/PageHeader';
import { PageContent } from '@/components/page/PageContent';

export default function BooksPage() {
  const { can, isModuleEnabled, bootstrap } = useTenantStore();
  const table = useServerTable();
  const { data, error, isLoading, refetch } = useLibraryBookList({
    page: table.queryParams.page,
    page_size: table.queryParams.page_size,
    search: table.queryParams.search,
  });

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
    <Page>
      <PageHeader
        title="Library Books"
        description="View and manage library book collection"
      />

      <PageContent>
        {!bootstrap || !isModuleEnabled('library') || !can('library.view') ? (
          <Alert severity="error">You do not have permission to view library books.</Alert>
        ) : (
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
        )}
      </PageContent>
    </Page>
  );
}
