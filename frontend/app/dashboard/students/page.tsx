/**
 * Students list page.
 *
 * Displays:
 * - Table of all students with search, filter, pagination
 * - Create button
 * - Edit/View/Delete actions
 * - Module/capability checks
 *
 * Demonstrates the new design system usage:
 * - Page wrapper for consistent layout
 * - PageHeader for title + description + actions
 * - ConfirmDialog for destructive actions
 */

'use client';

export const dynamic = 'force-dynamic';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useState } from 'react';
import { Box, Button, Alert, IconButton } from '@mui/material';
import { Add as AddIcon, Edit as EditIcon, Delete as DeleteIcon, Visibility as ViewIcon } from '@mui/icons-material';
import type { GridColDef } from '@mui/x-data-grid';
import { useTenantStore } from '@/lib/tenant/store';
import { useStudentList, useDeleteStudent, StudentListItem } from '@/features/students/hooks';
import { useServerTable } from '@/hooks/useServerTable';
import { DataTable } from '@/components/data-table/DataTable';
import { Page } from '@/components/page/Page';
import { PageHeader } from '@/components/page/PageHeader';
import { PageContent } from '@/components/page/PageContent';
import { ConfirmDialog } from '@/components/feedback/ConfirmDialog';
import { StatusBadge } from '@/components/data/StatusBadge';

export default function StudentsPage() {
  const router = useRouter();
  const { can, isModuleEnabled } = useTenantStore();

  const table = useServerTable({ initialOrdering: '-created_at' });
  const { data, isLoading, error, refetch } = useStudentList(table.queryParams);
  const deleteStudent = useDeleteStudent();

  // Confirm dialog state
  const [confirmDelete, setConfirmDelete] = useState<{ id: string; name: string } | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  const canEdit = can('students.update');
  const canDelete = can('students.delete');

  const handleDeleteStudent = async () => {
    if (!confirmDelete) return;

    setIsDeleting(true);
    try {
      await deleteStudent.mutateAsync(confirmDelete.id);
      setConfirmDelete(null);
      router.refresh();
    } catch (err) {
      console.error('Delete failed:', err);
    } finally {
      setIsDeleting(false);
    }
  };

  if (!isModuleEnabled('academics')) {
    return (
      <Page>
        <Alert severity="info">
          The Academics module is not enabled for your school. Contact your administrator to enable it.
        </Alert>
      </Page>
    );
  }

  if (!can('students.view')) {
    return (
      <Page>
        <Alert severity="error">
          You do not have permission to view students.
        </Alert>
      </Page>
    );
  }

  const columns: GridColDef<StudentListItem>[] = [
    { field: 'admission_no', headerName: 'Admission #', flex: 1, minWidth: 120 },
    { field: 'full_name', headerName: 'Name', flex: 1.5, minWidth: 160 },
    {
      field: 'gender',
      headerName: 'Gender',
      flex: 0.75,
      minWidth: 100,
      valueGetter: (params) =>
        params.row.gender ? params.row.gender.charAt(0).toUpperCase() + params.row.gender.slice(1) : '-',
    },
    {
      field: 'age',
      headerName: 'Age',
      flex: 0.5,
      minWidth: 80,
      valueGetter: (params) => (params.row.age ?? '-'),
    },
    {
      field: 'batch_name',
      headerName: 'Batch',
      flex: 1,
      minWidth: 120,
      valueGetter: (params) => params.row.batch_name || '-',
    },
    {
      field: 'is_active',
      headerName: 'Status',
      flex: 1,
      minWidth: 100,
      sortable: false,
      renderCell: (params) => (
        <StatusBadge
          status={params.row.is_active ? 'success' : 'error'}
          label={params.row.is_active ? 'Active' : 'Inactive'}
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
          <Link href={`/dashboard/students/${params.row.id}`} passHref legacyBehavior>
            <IconButton size="small" component="a" title="View">
              <ViewIcon fontSize="small" />
            </IconButton>
          </Link>
          {canEdit && (
            <Link href={`/dashboard/students/${params.row.id}/edit`} passHref legacyBehavior>
              <IconButton size="small" component="a" title="Edit">
                <EditIcon fontSize="small" />
              </IconButton>
            </Link>
          )}
          {canDelete && (
            <IconButton
              size="small"
              title="Delete"
              onClick={() => setConfirmDelete({ id: params.row.id, name: params.row.full_name })}
            >
              <DeleteIcon fontSize="small" color="error" />
            </IconButton>
          )}
        </Box>
      ),
    },
  ];

  return (
    <>
      <Page>
        <PageHeader
          title="Students"
          description="Manage students enrolled at your school."
          actions={
            can('students.create') && (
              <Link href="/dashboard/students/create" passHref legacyBehavior>
                <Button
                  component="a"
                  variant="contained"
                  startIcon={<AddIcon />}
                >
                  New Student
                </Button>
              </Link>
            )
          }
        />

        <PageContent>
          <DataTable<StudentListItem>
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
            searchPlaceholder="Search by name or admission number"
            emptyMessage="No students found"
          />
        </PageContent>
      </Page>

      {/* Delete confirmation dialog */}
      <ConfirmDialog
        open={Boolean(confirmDelete)}
        title="Delete student?"
        description={`Are you sure you want to delete ${confirmDelete?.name}? This action cannot be undone.`}
        confirmLabel="Delete"
        destructive
        loading={isDeleting}
        onConfirm={handleDeleteStudent}
        onCancel={() => setConfirmDelete(null)}
      />
    </>
  );
}
