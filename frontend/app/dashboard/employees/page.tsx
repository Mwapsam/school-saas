/**
 * Employees list page.
 *
 * Uses design system components:
 * - Page wrapper for consistent layout
 * - PageHeader for title and actions
 * - DataTable for employees list
 */

'use client';

export const dynamic = 'force-dynamic';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useState } from 'react';
import { Button, Alert, IconButton } from '@mui/material';
import { Box } from '@mui/material';
import {
  Add as AddIcon,
  Edit as EditIcon,
  Delete as DeleteIcon,
  Visibility as ViewIcon,
} from '@mui/icons-material';
import type { GridColDef } from '@mui/x-data-grid';
import { useTenantStore } from '@/lib/tenant/store';
import { useEmployeeList, useDeleteEmployee, type Employee } from '@/features/hr/hooks';
import { useServerTable } from '@/hooks/useServerTable';
import { DataTable } from '@/components/data-table/DataTable';
import { Page } from '@/components/page/Page';
import { PageHeader } from '@/components/page/PageHeader';
import { PageContent } from '@/components/page/PageContent';
import { ConfirmDialog } from '@/components/feedback/ConfirmDialog';

export default function EmployeesPage() {
  const router = useRouter();
  const { can, isModuleEnabled, bootstrap } = useTenantStore();
  const table = useServerTable();
  const { data, error, isLoading, refetch } = useEmployeeList(table.queryParams);
  const deleteEmployee = useDeleteEmployee();

  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);
  const [employeeToDelete, setEmployeeToDelete] = useState<{ id: string; name: string } | null>(null);

  const canEdit = can('hr.employees.update');
  const canDelete = can('hr.employees.delete');

  const handleDeleteEmployee = (id: string, name: string) => {
    setEmployeeToDelete({ id, name });
    setDeleteConfirmOpen(true);
  };

  const handleConfirmDelete = async () => {
    if (!employeeToDelete) return;
    try {
      await deleteEmployee.mutateAsync(employeeToDelete.id);
      setDeleteConfirmOpen(false);
      setEmployeeToDelete(null);
      router.refresh();
    } catch (err) {
      console.error('Delete failed:', err);
    }
  };

  const columns: GridColDef<Employee>[] = [
    { field: 'employee_number', headerName: 'Employee ID', flex: 1 },
    { field: 'full_name', headerName: 'Name', flex: 1.5 },
    { field: 'department_name', headerName: 'Department', flex: 1, valueGetter: (params) => params.row.department_name || '-' },
    { field: 'position_name', headerName: 'Position', flex: 1, valueGetter: (params) => params.row.position_name || '-' },
    {
      field: 'status',
      headerName: 'Status',
      flex: 0.8,
      valueGetter: (params) => (params.row.status ? 'Active' : 'Inactive'),
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
          <Link href={`/dashboard/employees/${params.row.id}`} passHref legacyBehavior>
            <IconButton size="small" component="a" title="View">
              <ViewIcon fontSize="small" />
            </IconButton>
          </Link>
          {canEdit && (
            <Link href={`/dashboard/employees/${params.row.id}/edit`} passHref legacyBehavior>
              <IconButton size="small" component="a" title="Edit">
                <EditIcon fontSize="small" />
              </IconButton>
            </Link>
          )}
          {canDelete && (
            <IconButton
              size="small"
              title="Delete"
              onClick={() => handleDeleteEmployee(params.row.id, params.row.full_name)}
            >
              <DeleteIcon fontSize="small" color="error" />
            </IconButton>
          )}
        </Box>
      ),
    },
  ];

  return (
    <Page>
      <PageHeader
        title="Employees"
        description="Manage staff and employee information"
        actions={
          can('hr.employees.create') && (
            <Link href="/dashboard/employees/create" passHref legacyBehavior>
              <Button component="a" variant="contained" startIcon={<AddIcon />}>
                New Employee
              </Button>
            </Link>
          )
        }
      />

      <PageContent>
        {!bootstrap || !isModuleEnabled('hr') || !can('hr.employees.view') ? (
          <Alert severity="error">
            You do not have permission to view employees.
          </Alert>
        ) : (
          <>
            <DataTable<Employee>
              rows={data?.results ?? []}
              columns={columns}
              rowCount={data?.count ?? 0}
              loading={isLoading}
              error={error as Error | null}
              onRetry={() => refetch()}
              paginationModel={table.paginationModel}
              onPaginationModelChange={table.onPaginationModelChange}
              onSortModelChange={(model) => table.onSortModelChange(model as Array<{ field: string; sort: 'asc' | 'desc' | null }>)}
              search={table.search}
              onSearchChange={table.onSearchChange}
              searchPlaceholder="Search employees..."
              emptyMessage="No employees found"
            />

            {employeeToDelete && (
              <ConfirmDialog
                open={deleteConfirmOpen}
                title="Delete Employee"
                message={`Are you sure you want to delete ${employeeToDelete.name}? This action cannot be undone.`}
                onConfirm={handleConfirmDelete}
                onCancel={() => {
                  setDeleteConfirmOpen(false);
                  setEmployeeToDelete(null);
                }}
                isDestructive
                isLoading={deleteEmployee.isPending}
              />
            )}
          </>
        )}
      </PageContent>
    </Page>
  );
}
