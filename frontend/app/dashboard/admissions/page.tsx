/**
 * Admissions applications list page.
 */

'use client';

export const dynamic = 'force-dynamic';

import Link from 'next/link';
import { Container, Box, Typography, Button, Alert, Chip } from '@mui/material';
import { Add as AddIcon } from '@mui/icons-material';
import type { GridColDef } from '@mui/x-data-grid';
import { useTenantStore } from '@/lib/tenant/store';
import { useAdmissionApplicationList, type AdmissionApplication } from '@/features/admissions/hooks';
import { useServerTable } from '@/hooks/useServerTable';
import { DataTable } from '@/components/data-table/DataTable';

export default function AdmissionsPage() {
  const { can, isModuleEnabled, bootstrap } = useTenantStore();
  const table = useServerTable();
  const { data, error, isLoading, refetch } = useAdmissionApplicationList({
    page: table.queryParams.page,
    page_size: table.queryParams.page_size,
    search: table.queryParams.search,
  });

  if (!bootstrap || !isModuleEnabled('admissions') || !can('admissions.application.view')) {
    return (
      <Container maxWidth="lg">
        <Box sx={{ py: 4 }}>
          <Alert severity="error">
            You do not have permission to view admissions.
          </Alert>
        </Box>
      </Container>
    );
  }

  const columns: GridColDef<AdmissionApplication>[] = [
    { field: 'application_number', headerName: 'Application #', flex: 1 },
    {
      field: 'student_name',
      headerName: 'Student Name',
      flex: 1.5,
      valueGetter: (params) => `${params.row.first_name} ${params.row.last_name}`,
    },
    { field: 'guardian_email', headerName: 'Guardian Email', flex: 1.5 },
    { field: 'course_name', headerName: 'Course', flex: 1 },
    {
      field: 'status',
      headerName: 'Status',
      flex: 1,
      sortable: false,
      renderCell: (params) => (
        <Chip
          label={params.row.status}
          color={params.row.status === 'approved' ? 'success' : params.row.status === 'rejected' ? 'error' : 'default'}
          size="small"
        />
      ),
    },
  ];

  return (
    <Container maxWidth="lg">
      <Box sx={{ py: 4 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
          <Typography variant="h4" component="h1">
            Admission Applications
          </Typography>
          {can('admissions.create') && (
            <Link href="/dashboard/admissions/create" passHref legacyBehavior>
              <Button component="a" variant="contained" startIcon={<AddIcon />}>
                New Application
              </Button>
            </Link>
          )}
        </Box>

        <DataTable<AdmissionApplication>
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
          searchPlaceholder="Search applications..."
          emptyMessage="No applications found"
        />
      </Box>
    </Container>
  );
}
