/**
 * Admissions applications list page.
 *
 * Reference implementation using design system:
 * - Page wrapper for consistent layout
 * - PageHeader for title and actions
 * - DataTable for applications list
 */

'use client';

export const dynamic = 'force-dynamic';

import Link from 'next/link';
import { Button, Alert, Typography } from '@mui/material';
import { Add as AddIcon } from '@mui/icons-material';
import type { GridColDef } from '@mui/x-data-grid';
import { useTenantStore } from '@/lib/tenant/store';
import { useAdmissionApplicationList, type AdmissionApplication } from '@/features/admissions/hooks';
import { useServerTable } from '@/hooks/useServerTable';
import { DataTable } from '@/components/data-table/DataTable';
import { Page } from '@/components/page/Page';
import { PageHeader } from '@/components/page/PageHeader';
import { PageContent } from '@/components/page/PageContent';
import { StatusBadge } from '@/components/data/StatusBadge';

export default function AdmissionsPage() {
  const { can, isModuleEnabled, bootstrap } = useTenantStore();
  const table = useServerTable();
  const { data, error, isLoading, refetch } = useAdmissionApplicationList({
    page: table.queryParams.page,
    page_size: table.queryParams.page_size,
    search: table.queryParams.search,
  });

  const columns: GridColDef<AdmissionApplication>[] = [
    {
      field: 'application_number',
      headerName: 'Application #',
      flex: 1,
      renderCell: (params) => (
        <Link href={`/dashboard/admissions/${params.row.id}`} passHref legacyBehavior>
          <Typography
            component="a"
            sx={{
              cursor: 'pointer',
              color: 'primary.main',
              textDecoration: 'none',
              '&:hover': { textDecoration: 'underline' },
            }}
          >
            {params.row.application_number}
          </Typography>
        </Link>
      ),
    },
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
      renderCell: (params) => {
        const status = params.row.status?.toLowerCase() ?? 'default';
        return <StatusBadge status={status as any} />;
      },
    },
  ];

  return (
    <Page>
      <PageHeader
        title="Admission Applications"
        description="Manage student admission applications and approvals"
        actions={
          can('admissions.create') && (
            <Link href="/dashboard/admissions/create" passHref legacyBehavior>
              <Button component="a" variant="contained" startIcon={<AddIcon />}>
                New Application
              </Button>
            </Link>
          )
        }
      />

      <PageContent>
        {!bootstrap || !isModuleEnabled('admissions') || !can('admissions.application.view') ? (
          <Alert severity="error">
            You do not have permission to view admissions.
          </Alert>
        ) : (
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
        )}
      </PageContent>
    </Page>
  );
}
