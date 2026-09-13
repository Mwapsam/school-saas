'use client';

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import {
  Container,
  Button,
  TextField,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TablePagination,
  Paper,
} from '@mui/material';
import { Download as DownloadIcon } from '@mui/icons-material';

import { Page } from '@/components/page/Page';
import { PageHeader } from '@/components/page/PageHeader';
import { PageContent } from '@/components/page/PageContent';
import { StatusBadge } from '@/components/data/StatusBadge';
import { LoadingState } from '@/components/feedback/LoadingState';
import { ErrorState } from '@/components/feedback/ErrorState';

import {
  useApplicationsForAssignment,
  useAdmissionStats,
  useApproveApplication,
  useRejectApplication,
  useDeleteApplication,
  useDuplicateApplication,
  useBulkStatusUpdate,
  useExportApplicationPdf,
} from '@/features/admission-management/hooks';

const AdmissionManagementPage: React.FC = () => {
  const router = useRouter();

  // Filters
  const [statusFilter, setStatusFilter] = useState('');
  const [academicYearFilter, setAcademicYearFilter] = useState('');
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);

  // Dialog states
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);
  const [selectedAppForDelete, setSelectedAppForDelete] = useState<string | null>(null);
  const [rejectDialogOpen, setRejectDialogOpen] = useState(false);
  const [selectedAppForReject, setSelectedAppForReject] = useState<string | null>(null);
  const [rejectReason, setRejectReason] = useState('');

  // Queries
  const { data: applications, isLoading, error } = useApplicationsForAssignment({
    page,
    page_size: pageSize,
    status: statusFilter,
    search: '',
  });
  const { data: stats } = useAdmissionStats();

  // Mutations
  const approveMutation = useApproveApplication(selectedAppForReject || '');
  const rejectMutation = useRejectApplication(selectedAppForReject || '');
  const deleteMutation = useDeleteApplication(selectedAppForDelete || '');
  const duplicateMutation = useDuplicateApplication(selectedAppForDelete || '');
  const exportMutation = useExportApplicationPdf(selectedAppForDelete || '');

  const handleApprove = async (appId: string) => {
    try {
      await useApproveApplication(appId).mutateAsync();
      router.refresh();
    } catch (err: any) {
      alert(err?.response?.data?.error || 'Failed to approve');
    }
  };

  const handleRejectClick = (appId: string) => {
    setSelectedAppForReject(appId);
    setRejectDialogOpen(true);
  };

  const handleRejectConfirm = async () => {
    if (!rejectReason.trim()) {
      alert('Rejection reason is required');
      return;
    }
    try {
      await rejectMutation.mutateAsync({ reason: rejectReason });
      setRejectDialogOpen(false);
      setRejectReason('');
      router.refresh();
    } catch (err: any) {
      alert(err?.response?.data?.error || 'Failed to reject');
    }
  };

  const handleDeleteClick = (appId: string) => {
    setSelectedAppForDelete(appId);
    setDeleteConfirmOpen(true);
  };

  const handleDeleteConfirm = async () => {
    try {
      await deleteMutation.mutateAsync();
      setDeleteConfirmOpen(false);
      router.refresh();
    } catch (err: any) {
      alert(err?.response?.data?.error || 'Failed to delete');
    }
  };

  const handleDuplicate = async (appId: string) => {
    try {
      const result = await useDuplicateApplication(appId).mutateAsync();
      const newId = (result as any)?.data?.id || (result as any)?.id;
      router.push(`/dashboard/admissions/multi-step/${newId}`);
    } catch (err: any) {
      alert(err?.response?.data?.error || 'Failed to duplicate');
    }
  };

  const handleExportPdf = async (appId: string) => {
    try {
      await useExportApplicationPdf(appId).mutateAsync();
      // Trigger download (implementation depends on backend response format)
    } catch (err: any) {
      alert(err?.response?.data?.error || 'Failed to export');
    }
  };

  const handleViewDetail = (appId: string) => {
    router.push(`/dashboard/admissions/${appId}`);
  };

  const handleAdmit = (appId: string) => {
    // Navigate to detail page where admit action is available
    router.push(`/dashboard/admissions/${appId}`);
  };

  if (isLoading) return <LoadingState />;
  if (error) return <ErrorState title="Failed to load applications" description="Please try again" />;

  return (
    <Page>
      <PageHeader title="Admission Management" description="Manage all admission applications" />

      <PageContent>
        <Container maxWidth="xl">
          {/* Filters */}
          <Stack direction="row" spacing={2} sx={{ mb: 3 }}>
            <FormControl sx={{ minWidth: 200 }}>
              <InputLabel>Status</InputLabel>
              <Select
                value={statusFilter}
                onChange={(e) => {
                  setStatusFilter(e.target.value);
                  setPage(1);
                }}
                label="Status"
              >
                <MenuItem value="">All Statuses</MenuItem>
                <MenuItem value="draft">Draft</MenuItem>
                <MenuItem value="submitted">Submitted</MenuItem>
                <MenuItem value="under_review">Under Review</MenuItem>
                <MenuItem value="approved">Approved</MenuItem>
                <MenuItem value="admitted">Admitted</MenuItem>
                <MenuItem value="rejected">Rejected</MenuItem>
              </Select>
            </FormControl>

            <Button
              variant="outlined"
              onClick={() => {
                setStatusFilter('');
                setAcademicYearFilter('');
                setPage(1);
              }}
            >
              Clear Filters
            </Button>
          </Stack>

          {/* Data Table */}
          <TableContainer component={Paper}>
            <Table>
              <TableHead>
                <TableRow>
                  <TableCell>Application #</TableCell>
                  <TableCell>Name</TableCell>
                  <TableCell>Course</TableCell>
                  <TableCell>Status</TableCell>
                  <TableCell>Applied Date</TableCell>
                  <TableCell align="right">Actions</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {applications?.results?.map((row: any) => (
                  <TableRow key={row.id}>
                    <TableCell>{row.application_number}</TableCell>
                    <TableCell>{row.full_name}</TableCell>
                    <TableCell>{row.course_applied?.course_name || '-'}</TableCell>
                    <TableCell><StatusBadge status={row.status} /></TableCell>
                    <TableCell>{new Date(row.application_date).toLocaleDateString()}</TableCell>
                    <TableCell align="right">
                      <Stack direction="row" spacing={1} sx={{ justifyContent: 'flex-end' }}>
                        <Button size="small" variant="outlined" onClick={() => handleViewDetail(row.id)}>
                          View
                        </Button>
                        <Button size="small" variant="outlined" onClick={() => router.push(`/dashboard/admissions/multi-step/${row.id}?edit=true`)}>
                          Edit
                        </Button>
                        {(row.status === 'submitted' || row.status === 'under_review') && (
                          <>
                            <Button size="small" variant="contained" color="success" onClick={() => handleApprove(row.id)}>
                              Approve
                            </Button>
                            <Button size="small" variant="outlined" color="error" onClick={() => handleRejectClick(row.id)}>
                              Reject
                            </Button>
                          </>
                        )}
                        {row.status === 'approved' && (
                          <Button size="small" variant="contained" color="success" onClick={() => handleAdmit(row.id)}>
                            Admit
                          </Button>
                        )}
                        <Button size="small" variant="outlined" onClick={() => handleDuplicate(row.id)}>
                          Dup
                        </Button>
                        <Button size="small" variant="outlined" startIcon={<DownloadIcon />} onClick={() => handleExportPdf(row.id)}>
                          PDF
                        </Button>
                        <Button size="small" variant="outlined" color="error" onClick={() => handleDeleteClick(row.id)}>
                          Delete
                        </Button>
                      </Stack>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
            <TablePagination
              rowsPerPageOptions={[10, 25, 50]}
              component="div"
              count={applications?.count || 0}
              rowsPerPage={pageSize}
              page={page - 1}
              onPageChange={(_, newPage) => setPage(newPage + 1)}
              onRowsPerPageChange={(e) => {
                setPageSize(parseInt(e.target.value, 10));
                setPage(1);
              }}
            />
          </TableContainer>
        </Container>
      </PageContent>

      {/* Delete Confirmation Dialog */}
      <Dialog open={deleteConfirmOpen} onClose={() => setDeleteConfirmOpen(false)}>
        <DialogTitle>Delete Application</DialogTitle>
        <DialogContent>
          Are you sure you want to delete this application? This action cannot be undone.
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDeleteConfirmOpen(false)}>Cancel</Button>
          <Button
            onClick={handleDeleteConfirm}
            color="error"
            variant="contained"
            disabled={deleteMutation.isPending}
          >
            Delete
          </Button>
        </DialogActions>
      </Dialog>

      {/* Reject Dialog */}
      <Dialog open={rejectDialogOpen} onClose={() => setRejectDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Reject Application</DialogTitle>
        <DialogContent>
          <TextField
            autoFocus
            margin="dense"
            label="Rejection Reason"
            type="text"
            fullWidth
            multiline
            rows={4}
            value={rejectReason}
            onChange={(e) => setRejectReason(e.target.value)}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setRejectDialogOpen(false)}>Cancel</Button>
          <Button
            onClick={handleRejectConfirm}
            color="error"
            variant="contained"
            disabled={rejectMutation.isPending}
          >
            Reject
          </Button>
        </DialogActions>
      </Dialog>
    </Page>
  );
};

export default AdmissionManagementPage;
