/**
 * Applicants management page — batch assignment, status management, diagnostics.
 * Uses design system components.
 */

'use client';

export const dynamic = 'force-dynamic';

import { useState } from 'react';
import Link from 'next/link';
import { Box, Button, Alert, Dialog, DialogTitle, DialogContent, DialogActions, TextField, CircularProgress, Grid, Paper, MenuItem, Typography } from '@mui/material';
import { Assignment as AssignIcon } from '@mui/icons-material';
import type { GridColDef } from '@mui/x-data-grid';
import { useTenantStore } from '@/lib/tenant/store';
import {
  useApplicationsForAssignment,
  useAvailableBatches,
  useAdmissionStats,
  useAssignSingle,
  useAssignBulk,
  type ApplicantForAssignment,
} from '@/features/admission-management';
import { useServerTable } from '@/hooks/useServerTable';
import { DataTable } from '@/components/data-table/DataTable';
import { Page } from '@/components/page/Page';
import { PageHeader } from '@/components/page/PageHeader';
import { PageContent } from '@/components/page/PageContent';
import { StatusBadge } from '@/components/data/StatusBadge';

export default function ApplicantsPage() {
  const { can, isModuleEnabled, bootstrap } = useTenantStore();
  const table = useServerTable();
  const [selectedRows, setSelectedRows] = useState<string[]>([]);
  const [bulkAssignOpen, setBulkAssignOpen] = useState(false);
  const [selectedBatchForBulk, setSelectedBatchForBulk] = useState('');

  const { data, error, isLoading, refetch } = useApplicationsForAssignment({
    page: table.queryParams.page,
    page_size: table.queryParams.page_size,
    search: table.queryParams.search,
  });

  const { data: batches } = useAvailableBatches();
  const { data: stats } = useAdmissionStats();
  const assignSingleMutation = useAssignSingle();
  const assignBulkMutation = useAssignBulk();

  if (!bootstrap || !isModuleEnabled('admissions') || !can('admissions.application.manage')) {
    return (
      <Page>
        <Alert severity="error">You do not have permission to manage applicants.</Alert>
      </Page>
    );
  }

  const handleBulkAssign = async () => {
    if (!selectedBatchForBulk || selectedRows.length === 0) {
      alert('Please select a batch and applications');
      return;
    }

    const assignments = selectedRows.map((appId) => ({
      application_id: appId,
      batch_id: selectedBatchForBulk,
      roll_number: '',
    }));

    try {
      await assignBulkMutation.mutateAsync({ assignments });
      setSelectedRows([]);
      setBulkAssignOpen(false);
    } catch (err) {
      console.error('Bulk assignment failed:', err);
    }
  };

  const columns: GridColDef<ApplicantForAssignment>[] = [
    {
      field: 'application_number',
      headerName: 'Application #',
      flex: 1,
      renderCell: (params) => (
        <Link href={`/dashboard/admissions/multi-step/${params.row.id}`} passHref legacyBehavior>
          <Typography component="a" sx={{ cursor: 'pointer', color: 'primary.main', textDecoration: 'none', '&:hover': { textDecoration: 'underline' } }}>
            {params.row.application_number}
          </Typography>
        </Link>
      ),
    },
    {
      field: 'full_name',
      headerName: 'Name',
      flex: 1.5,
      valueGetter: (params) => `${params.row.first_name} ${params.row.last_name}`,
    },
    {
      field: 'email',
      headerName: 'Email',
      flex: 1.5,
    },
    {
      field: 'status',
      headerName: 'Status',
      flex: 1,
      sortable: false,
      renderCell: (params) => (
        <StatusBadge status={params.row.status || 'unknown'} />
      ),
    },
    {
      field: 'course_applied',
      headerName: 'Course',
      flex: 1.5,
      valueGetter: (params) => params.row.course_applied?.course_name || '-',
    },
    {
      field: 'application_date',
      headerName: 'Applied',
      flex: 1,
      valueGetter: (params) => new Date(params.row.application_date).toLocaleDateString(),
    },
  ];

  return (
    <Page>
      <PageHeader
        title="Applicants"
        description="Manage applications and batch assignments"
        actions={
          selectedRows.length > 0 && (
            <Button
              variant="contained"
              color="success"
              startIcon={<AssignIcon />}
              onClick={() => setBulkAssignOpen(true)}
            >
              Assign ({selectedRows.length})
            </Button>
          )
        }
      />

      <PageContent>
        {/* Stats Cards */}
        {stats && (
          <Grid container spacing={2} sx={{ mb: 3 }}>
            <Grid item xs={12} sm={6} md={3}>
              <Paper sx={{ p: 2 }}>
                <Typography color="textSecondary" variant="body2" gutterBottom>
                  Total Applications
                </Typography>
                <Typography variant="h6">{stats.total_applications}</Typography>
              </Paper>
            </Grid>
            <Grid item xs={12} sm={6} md={3}>
              <Paper sx={{ p: 2 }}>
                <Typography color="textSecondary" variant="body2" gutterBottom>
                  Approved
                </Typography>
                <Typography variant="h6" color="warning.main">
                  {stats.approved_applications}
                </Typography>
              </Paper>
            </Grid>
            <Grid item xs={12} sm={6} md={3}>
              <Paper sx={{ p: 2 }}>
                <Typography color="textSecondary" variant="body2" gutterBottom>
                  Admitted
                </Typography>
                <Typography variant="h6" color="success.main">
                  {stats.admitted_applications}
                </Typography>
              </Paper>
            </Grid>
            <Grid item xs={12} sm={6} md={3}>
              <Paper sx={{ p: 2 }}>
                <Typography color="textSecondary" variant="body2" gutterBottom>
                  Pending Review
                </Typography>
                <Typography variant="h6" color="info.main">
                  {stats.pending_review}
                </Typography>
              </Paper>
            </Grid>
          </Grid>
        )}

        {/* DataTable */}
        <DataTable<ApplicantForAssignment>
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
          checkboxSelection
          onSelectionChange={(newSelection) => setSelectedRows(newSelection as string[])}
        />
      </PageContent>

      {/* Bulk Assignment Dialog */}
      <Dialog open={bulkAssignOpen} onClose={() => setBulkAssignOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Assign to Batch</DialogTitle>
        <DialogContent sx={{ pt: 2 }}>
          <Typography variant="body2" color="textSecondary" sx={{ mb: 2 }}>
            Assigning {selectedRows.length} application(s) to a batch
          </Typography>
          <TextField
            select
            fullWidth
            label="Select Batch"
            value={selectedBatchForBulk}
            onChange={(e) => setSelectedBatchForBulk(e.target.value)}
          >
            {batches?.map((batch) => (
              <MenuItem key={batch.id} value={batch.id}>
                {batch.name} {batch.section_name && `- ${batch.section_name}`}
              </MenuItem>
            ))}
          </TextField>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setBulkAssignOpen(false)}>Cancel</Button>
          <Button
            onClick={handleBulkAssign}
            variant="contained"
            color="success"
            disabled={!selectedBatchForBulk || assignBulkMutation.isPending}
            startIcon={assignBulkMutation.isPending && <CircularProgress size={20} />}
          >
            {assignBulkMutation.isPending ? 'Assigning...' : 'Assign'}
          </Button>
        </DialogActions>
      </Dialog>
    </Page>
  );
}
