/**
 * Students list page.
 *
 * Displays:
 * - Table of all students
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
import { useStudentList, useDeleteStudent, StudentListItem } from '@/features/students/hooks';
import { useServerTable } from '@/hooks/useServerTable';
import { DataTable } from '@/components/data-table/DataTable';

export default function StudentsPage() {
  const router = useRouter();
  const { can, isModuleEnabled } = useTenantStore();

  const table = useServerTable({ initialOrdering: '-created_at' });
  const { data, isLoading, error, refetch } = useStudentList(table.queryParams);
  const deleteStudent = useDeleteStudent();

  const canEdit = can('students.update');
  const canDelete = can('students.delete');

  const handleDeleteStudent = async (id: string, name: string) => {
    if (!window.confirm(`Delete ${name}?`)) return;
    try {
      await deleteStudent.mutateAsync(id);
      router.refresh();
    } catch (err) {
      console.error('Delete failed:', err);
    }
  };

  if (!isModuleEnabled('academics')) {
    return (
      <Container maxWidth="lg">
        <Box sx={{ py: 4 }}>
          <Alert severity="info">
            The Academics module is not enabled for your school. Contact your administrator to enable it.
          </Alert>
        </Box>
      </Container>
    );
  }

  if (!can('students.view')) {
    return (
      <Container maxWidth="lg">
        <Box sx={{ py: 4 }}>
          <Alert severity="error">
            You do not have permission to view students.
          </Alert>
        </Box>
      </Container>
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
              onClick={() => handleDeleteStudent(params.row.id, params.row.full_name)}
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
            Students
          </Typography>
          {can('students.create') && (
            <Link href="/dashboard/students/create" passHref legacyBehavior>
              <Button
                component="a"
                variant="contained"
                startIcon={<AddIcon />}
              >
                New Student
              </Button>
            </Link>
          )}
        </Box>

        {/* Table */}
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
      </Box>
    </Container>
  );
}
