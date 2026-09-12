/**
 * Applicant enquiries list page.
 */

'use client';

export const dynamic = 'force-dynamic';

import Link from 'next/link';
import { Container, Box, Typography, Button, Alert, Chip } from '@mui/material';
import { Add as AddIcon } from '@mui/icons-material';
import type { GridColDef } from '@mui/x-data-grid';
import { useTenantStore } from '@/lib/tenant/store';
import { useEnquiryList, type ApplicantEnquiry } from '@/features/enquiries';
import { useServerTable } from '@/hooks/useServerTable';
import { DataTable } from '@/components/data-table/DataTable';

export default function InquiriesPage() {
  const { can, isModuleEnabled, bootstrap } = useTenantStore();
  const table = useServerTable();
  const { data, error, isLoading, refetch } = useEnquiryList({
    page: table.queryParams.page,
    page_size: table.queryParams.page_size,
    search: table.queryParams.search,
  });

  if (!bootstrap || !isModuleEnabled('admissions') || !can('admissions.enquiry.view')) {
    return (
      <Container maxWidth="lg">
        <Box sx={{ py: 4 }}>
          <Alert severity="error">
            You do not have permission to view enquiries.
          </Alert>
        </Box>
      </Container>
    );
  }

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
    <Container maxWidth="lg">
      <Box sx={{ py: 4 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
          <Typography variant="h4" component="h1">
            Applicant Enquiries
          </Typography>
          {can('admissions.enquiry.manage') && (
            <Link href="/dashboard/inquiries/create" passHref legacyBehavior>
              <Button component="a" variant="contained" startIcon={<AddIcon />}>
                New Enquiry
              </Button>
            </Link>
          )}
        </Box>

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
      </Box>
    </Container>
  );
}
