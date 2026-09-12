/**
 * Fee categories list page.
 *
 * Displays:
 * - Table of all fee categories
 * - Search and filter controls
 * - Pagination
 * - Create button
 * - Module/capability checks
 */

'use client';

export const dynamic = 'force-dynamic';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { Container, Box, Typography, Button, Alert, Chip, IconButton } from '@mui/material';
import { Add as AddIcon, Edit as EditIcon, Delete as DeleteIcon, Visibility as ViewIcon } from '@mui/icons-material';
import type { GridColDef } from '@mui/x-data-grid';
import { useTenantStore } from '@/lib/tenant/store';
import { useFeeCategoryList, useDeleteFeeCategory, FeeCategory } from '@/features/finance/hooks';
import { useServerTable } from '@/hooks/useServerTable';
import { DataTable } from '@/components/data-table/DataTable';

export default function FeeCategoriesPage() {
  const router = useRouter();
  const { can, isModuleEnabled } = useTenantStore();

  const table = useServerTable({ initialOrdering: 'name' });
  const { data, isLoading, error, refetch } = useFeeCategoryList(table.queryParams);
  const deleteFeeCategory = useDeleteFeeCategory();

  const canEdit = can('finance.fees.manage');
  const canDelete = can('finance.fees.manage');

  const handleDelete = async (id: string, name: string) => {
    if (!window.confirm(`Delete ${name}?`)) return;
    try {
      await deleteFeeCategory.mutateAsync(id);
      router.refresh();
    } catch (err) {
      console.error('Delete failed:', err);
    }
  };

  if (!isModuleEnabled('finance')) {
    return (
      <Container maxWidth="lg">
        <Box sx={{ py: 4 }}>
          <Alert severity="info">
            The Finance module is not enabled for your school. Contact your administrator to enable it.
          </Alert>
        </Box>
      </Container>
    );
  }

  if (!can('finance.fees.view')) {
    return (
      <Container maxWidth="lg">
        <Box sx={{ py: 4 }}>
          <Alert severity="error">
            You do not have permission to view fee categories.
          </Alert>
        </Box>
      </Container>
    );
  }

  const columns: GridColDef<FeeCategory>[] = [
    { field: 'name', headerName: 'Name', flex: 1.5, minWidth: 160 },
    {
      field: 'description',
      headerName: 'Description',
      flex: 2,
      minWidth: 200,
      valueGetter: (params) => params.row.description || '-',
    },
    {
      field: 'is_active',
      headerName: 'Status',
      flex: 1,
      minWidth: 100,
      sortable: false,
      renderCell: (params) => (
        <Chip
          label={params.row.is_active ? 'Active' : 'Inactive'}
          color={params.row.is_active ? 'success' : 'error'}
          size="small"
        />
      ),
    },
    {
      field: 'actions',
      headerName: 'Actions',
      flex: 1,
      minWidth: 130,
      sortable: false,
      filterable: false,
      align: 'right',
      headerAlign: 'right',
      renderCell: (params) => (
        <Box>
          <Link href={`/dashboard/invoices/fee-categories/${params.row.id}`} passHref legacyBehavior>
            <IconButton size="small" component="a" title="View">
              <ViewIcon fontSize="small" />
            </IconButton>
          </Link>
          {canEdit && (
            <Link href={`/dashboard/invoices/fee-categories/${params.row.id}/edit`} passHref legacyBehavior>
              <IconButton size="small" component="a" title="Edit">
                <EditIcon fontSize="small" />
              </IconButton>
            </Link>
          )}
          {canDelete && (
            <IconButton
              size="small"
              title="Delete"
              onClick={() => handleDelete(params.row.id, params.row.name)}
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
        {/* Header */}
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
          <Typography variant="h4" component="h1">
            Fee Categories
          </Typography>
          {can('finance.fees.manage') && (
            <Link href="/dashboard/invoices/fee-categories/create" passHref legacyBehavior>
              <Button
                component="a"
                variant="contained"
                startIcon={<AddIcon />}
              >
                New Fee Category
              </Button>
            </Link>
          )}
        </Box>

        {/* Table */}
        <DataTable<FeeCategory>
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
          searchPlaceholder="Search by name"
          emptyMessage="No fee categories found"
        />
      </Box>
    </Container>
  );
}
