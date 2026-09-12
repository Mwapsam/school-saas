/**
 * Applicant enquiries list page.
 *
 * Uses design system components:
 * - Page wrapper for consistent layout
 * - PageHeader for title and actions
 * - DataTable for enquiries list
 */

'use client';

export const dynamic = 'force-dynamic';

import Link from 'next/link';
import { Button, Alert, Chip } from '@mui/material';
import { Add as AddIcon } from '@mui/icons-material';
import type { GridColDef } from '@mui/x-data-grid';
import { useTenantStore } from '@/lib/tenant/store';
import { useEnquiryList, type ApplicantEnquiry } from '@/features/enquiries';
import { useServerTable } from '@/hooks/useServerTable';
import { DataTable } from '@/components/data-table/DataTable';
import { Page } from '@/components/page/Page';
import { PageHeader } from '@/components/page/PageHeader';
import { PageContent } from '@/components/page/PageContent';

export default function InquiriesPage() {
  const { can, isModuleEnabled, bootstrap } = useTenantStore();
  const table = useServerTable();
  const { data, error, isLoading, refetch } = useEnquiryList({
    page: table.queryParams.page,
    page_size: table.queryParams.page_size,
    search: table.queryParams.search,
  });

  const columns: GridColDef<ApplicantEnquiry>[] = [
    {
      field: 'enquiry_number',
      headerName: 'Enquiry #',
      flex: 1,
      renderCell: (params) => (
        <Link href={`/dashboard/inquiries/${params.row.id}`} passHref legacyBehavior>
          <Typography component="a" sx={{ cursor: 'pointer', color: 'primary.main', textDecoration: 'none', '&:hover': { textDecoration: 'underline' } }}>
            {params.row.enquiry_number}
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
    { field: 'email', headerName: 'Email', flex: 1.5 },
    { field: 'phone', headerName: 'Phone', flex: 1 },
    {
      field: 'stage_name',
      headerName: 'Stage',
      flex: 1,
      sortable: false,
      renderCell: (params) => (
        <Chip
          label={params.row.stage_name}
          size="small"
          sx={{ backgroundColor: params.row.stage_color || '#007bff', color: 'white' }}
        />
      ),
    },
    {
      field: 'enquired_date',
      headerName: 'Enquired Date',
      flex: 1,
      valueGetter: (params) => new Date(params.row.enquired_date).toLocaleDateString(),
    },
  ];

  return (
    <Page>
      <PageHeader
        title="Applicant Enquiries"
        description="Manage student enquiries and applications"
        actions={
          can('admissions.enquiry.manage') && (
            <Link href="/dashboard/inquiries/create" passHref legacyBehavior>
              <Button component="a" variant="contained" startIcon={<AddIcon />}>
                New Enquiry
              </Button>
            </Link>
          )
        }
      />

      <PageContent>
        {!bootstrap || !isModuleEnabled('admissions') || !can('admissions.enquiry.view') ? (
          <Alert severity="error">
            You do not have permission to view enquiries.
          </Alert>
        ) : (
          <DataTable<ApplicantEnquiry>
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
            searchPlaceholder="Search enquiries..."
            emptyMessage="No enquiries found"
          />
        )}
      </PageContent>
    </Page>
  );
}
